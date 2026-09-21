#!/usr/bin/env python3
"""Raw Zenoh recording and timed replay. No GUI or plotting dependencies."""
from __future__ import annotations

import json
import queue
import sqlite3
import threading
import time
from pathlib import Path

FORMAT = 'uesim-zenoh-recording-v1'


def open_session(endpoint, mode='client'):
    import zenoh
    config = zenoh.Config()
    config.insert_json5('mode', json.dumps(mode))
    if endpoint:
        config.insert_json5('connect/endpoints', json.dumps([endpoint]))
        config.insert_json5('scouting/multicast/enabled', 'false')
    return zenoh.open(config)


def read_connection(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        meta = dict(conn.execute('SELECT key, value FROM metadata'))
        if meta.get('format') != FORMAT:
            raise ValueError('不是支持的 UeSim 录制文件')
        return conn, meta
    except Exception:
        conn.close()
        raise


def inspect_recording(path):
    conn, meta = read_connection(path)
    try:
        rows = conn.execute('SELECT topic, COUNT(*), SUM(length(payload)) FROM messages GROUP BY topic').fetchall()
        duration = conn.execute('SELECT COALESCE(MAX(time_ns), 0) FROM messages').fetchone()[0]
        return meta, rows, duration / 1e9
    finally:
        conn.close()


class Recorder:
    """Bounded async writer; stop drains accepted packets before final commit."""
    def __init__(self, path, topics, max_bytes=128 * 1024 * 1024):
        self.path = Path(path)
        self.topics = topics
        self.max_bytes = max_bytes
        self.lock = threading.Lock()
        self.pending = queue.Queue()
        self.queued_bytes = 0
        self.accepting = True
        self.error = None
        self.count = 0
        self.bytes = 0
        self.dropped = 0
        self.ready = threading.Event()
        self.started_ns = time.monotonic_ns()
        # Exclusive creation prevents accidentally replacing an earlier recording.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('xb'):
            pass
        self.thread = threading.Thread(target=self._write, daemon=True)
        self.thread.start()
        self.ready.wait()
        if self.error:
            raise RuntimeError(self.error)

    def submit(self, topic, payload, encoding):
        with self.lock:
            if not self.accepting:
                return
            if self.queued_bytes + len(payload) > self.max_bytes:
                self.dropped += 1
                self.error = '磁盘写入跟不上数据：录制已停止（队列已满），文件标记为不完整'
                self.accepting = False
                self.pending.put(None)
                return
            elapsed = time.monotonic_ns() - self.started_ns
            self.queued_bytes += len(payload)
            self.pending.put((elapsed, topic, encoding, payload))

    def stop(self):
        with self.lock:
            if self.accepting:
                self.accepting = False
                self.pending.put(None)
        self.thread.join()
        if self.error:
            raise RuntimeError(self.error)

    def _write(self):
        conn = None
        try:
            conn = sqlite3.connect(self.path)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=FULL')
            conn.executescript('''
                CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE messages(id INTEGER PRIMARY KEY, time_ns INTEGER NOT NULL,
                    topic TEXT NOT NULL, encoding TEXT NOT NULL, payload BLOB NOT NULL);
            ''')
            meta = {'format': FORMAT, 'complete': 'false', 'created_unix_ns': str(time.time_ns()),
                    'topics': json.dumps(self.topics), 'time_basis': 'monotonic receive time',
                    'dropped': '0'}
            conn.executemany('INSERT INTO metadata VALUES (?, ?)', meta.items())
            conn.commit()
            self.ready.set()
            last_commit = time.monotonic()
            batch = 0
            while True:
                try:
                    item = self.pending.get(timeout=0.25)
                except queue.Empty:
                    conn.commit()
                    batch = 0
                    last_commit = time.monotonic()
                    continue
                if item is None:
                    break
                conn.execute('INSERT INTO messages(time_ns, topic, encoding, payload) VALUES (?, ?, ?, ?)', item)
                with self.lock:
                    self.queued_bytes -= len(item[3])
                    self.count += 1
                    self.bytes += len(item[3])
                batch += 1
                if batch >= 100 or time.monotonic() - last_commit >= 0.25:
                    conn.commit()
                    batch = 0
                    last_commit = time.monotonic()
            conn.execute('UPDATE metadata SET value=? WHERE key="complete"', ('false' if self.error else 'true',))
            conn.execute('UPDATE metadata SET value=? WHERE key="dropped"', (str(self.dropped),))
            conn.commit()
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        except Exception as exc:
            with self.lock:
                self.error = f'录制失败：{exc}'
                self.accepting = False
        finally:
            self.ready.set()
            if conn is not None:
                conn.close()


class Player:
    """Streaming replay; pause and stop interrupt even long inter-packet waits."""
    def __init__(self, path, callback, speed=1.0, session=None):
        if not 0.05 <= speed <= 16:
            raise ValueError('播放速度必须为 0.05–16 倍')
        self.path, self.callback, self.speed, self.session = path, callback, speed, session
        self.condition = threading.Condition()
        self.paused = False
        self.stopped = False
        self.done = threading.Event()
        self.error = None
        self.position = 0.0
        self.count = 0
        self.anchor = 0.0
        self.pause_start = 0.0
        self.thread = threading.Thread(target=self._play, daemon=True)

    def start(self):
        self.thread.start()

    def pause(self, value):
        with self.condition:
            if value != self.paused:
                now = time.monotonic()
                if value:
                    self.pause_start = now
                else:
                    self.anchor += now - self.pause_start
                self.paused = value
                self.condition.notify_all()

    def stop(self):
        with self.condition:
            self.stopped = True
            self.condition.notify_all()
        self.thread.join()

    def _play(self):
        conn = None
        try:
            conn, _ = read_connection(self.path)
            with self.condition:
                self.anchor = time.monotonic()
                if self.paused:
                    self.pause_start = self.anchor
            for elapsed, topic, encoding, payload in conn.execute(
                'SELECT time_ns, topic, encoding, payload FROM messages ORDER BY id'
            ):
                with self.condition:
                    while not self.stopped:
                        if self.paused:
                            self.condition.wait()
                            continue
                        remaining = self.anchor + elapsed / 1e9 / self.speed - time.monotonic()
                        if remaining <= 0:
                            break
                        self.condition.wait(timeout=min(remaining, 1.0))
                    if self.stopped:
                        break
                if self.session is not None:
                    self.session.put(topic, payload, encoding=encoding)
                self.callback(topic, payload, encoding)
                self.position = elapsed / 1e9
                self.count += 1
        except Exception as exc:
            self.error = f'播放失败：{exc}'
        finally:
            if conn is not None:
                conn.close()
            self.done.set()
