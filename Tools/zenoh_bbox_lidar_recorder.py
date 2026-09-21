#!/usr/bin/env python3
"""Chinese Tk UI for raw bbox/LiDAR recording, offline preview and Zenoh replay.

Run: python3 Tools/zenoh_bbox_lidar_recorder.py
Dependencies: eclipse-zenoh; Linux also needs python3-tk.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import queue
import struct
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from zenoh_recording import Player, Recorder, inspect_recording, open_session

ROOT = Path(__file__).resolve().parents[1]
CAMERA_TOPIC = 'rt/front_camera/image/compressed'


def detect_topics(endpoint, expression='**', duration=3.0):
    """Observe active topics without retaining payloads or creating a recording."""
    stats = {}
    lock = threading.Lock()

    def receive(sample):
        topic, size = str(sample.key_expr), len(sample.payload)
        with lock:
            count, total = stats.get(topic, (0, 0))
            stats[topic] = count + 1, total + size

    session = open_session(endpoint)
    try:
        subscriber = session.declare_subscriber(expression, receive)
        try:
            time.sleep(duration)
        finally:
            subscriber.undeclare()
    finally:
        session.close()
    with lock:
        return dict(sorted(stats.items()))


def compressed_image(data):
    """Extract JPEG/PNG bytes from ROS2 CompressedImage XCDR1 or raw images."""
    if data.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n')):
        return data, ''
    if data[:4] not in (b'\x00\x01\x00\x00', b'\x00\x00\x00\x00'):
        raise ValueError('不支持的 CompressedImage 封装')
    endian = '<' if data[1] else '>'
    offset = 4

    def number():
        nonlocal offset
        offset = (offset + 3) // 4 * 4
        if offset + 4 > len(data):
            raise ValueError('图像消息被截断')
        value = struct.unpack_from(endian + 'I', data, offset)[0]
        offset += 4
        return value

    def string():
        nonlocal offset
        size = number()
        if size < 1 or offset + size > len(data) or data[offset + size - 1] != 0:
            raise ValueError('无效的图像 CDR 字符串')
        value = data[offset:offset + size - 1].decode('utf-8')
        offset += size
        return value

    number()
    if number() >= 1000000000:
        raise ValueError('无效的图像时间戳')
    frame_id = string()
    string()  # format; Pillow detects JPEG/PNG from the encoded bytes.
    size = number()
    if size < 1 or offset + size > len(data):
        raise ValueError('图像数据长度错误')
    return data[offset:offset + size], frame_id


def camera_preview(payload, size):
    from PIL import Image
    encoded, frame_id = compressed_image(payload)
    with Image.open(io.BytesIO(encoded)) as source:
        if source.format not in ('JPEG', 'PNG'):
            raise ValueError('图像预览仅支持 JPEG/PNG')
        original_size = source.size
        source.thumbnail(size)
        return source.convert('RGB'), original_size, frame_id


def is_camera_topic(topic):
    return topic.rstrip('/').endswith('/image/compressed')


def default_topics():
    topics = ['rt/dynamicinfo']
    path = ROOT / 'UeSim/Content/model/config/sensors/config_data.json'
    try:
        for sensor in json.loads(path.read_text()).values():
            if sensor.get('enabled', True) and sensor.get('sensor_type', '').lower() in ('lidar', 'mid360', 'airy'):
                topic = sensor.get('topic', '').strip('/')
                if topic:
                    topics.append(topic if topic.startswith('rt/') else 'rt/' + topic)
    except (OSError, ValueError, AttributeError):
        pass
    if len(topics) == 1:
        topics.append('rt/front_lidar')
    return list(dict.fromkeys(topics + [CAMERA_TOPIC]))


def bbox_shapes(payload, include_metadata=False):
    """Read actor-keyed/double-encoded JSON using the same XY convention as bbox viewer."""
    shapes = []

    def visit(obj, name='', depth=0, metadata=None):
        if depth > 12:
            return
        if isinstance(obj, str):
            try:
                visit(json.loads(obj), name, depth + 1, metadata)
            except ValueError:
                pass
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                visit(item, str(i), depth + 1, metadata)
        elif isinstance(obj, dict):
            info = dict(metadata or {})
            for key in ('velocity', 'speed', 'velocity_unit'):
                if key in obj:
                    info[key] = obj[key]
            for key in ('category', 'Category', 'type', 'class'):
                if key in obj:
                    info['category'] = str(obj[key]).lower()
                    break
            if 'center' in obj and 'extent' in obj:
                try:
                    c, e, f = obj['center'], obj['extent'], obj.get('forward', {'x': 1, 'y': 0})
                    x, y = float(c['x']), float(c['y'])
                    ex, ey = abs(float(e['x'])), abs(float(e['y']))
                    fx, fy = float(f['x']), float(f['y'])
                    if not all(math.isfinite(v) for v in (x, y, ex, ey, fx, fy)):
                        return
                    norm = math.hypot(fx, fy)
                    fx, fy = (fx / norm, fy / norm) if norm > 1e-9 else (1, 0)
                    corners = [(x + a * ex * fx - b * ey * fy, y + a * ex * fy + b * ey * fx)
                               for a, b in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
                    shape = (str(obj.get('label', obj.get('name', obj.get('id', name)))), corners)
                    if include_metadata:
                        from bbox_motion import parse_motion
                        velocity, speed = parse_motion(info)
                        shape += (info.get('category', 'unknown'), velocity, speed)
                    shapes.append(shape)
                except (KeyError, TypeError, ValueError):
                    pass
            else:
                for key, item in obj.items():
                    if key in ('velocity', 'speed', 'velocity_unit', 'category', 'Category'):
                        continue
                    visit(item, name if key == 'bbox' else key, depth + 1, info)
    visit(json.loads(payload.decode('utf-8').strip('\x00 \r\n\t')))
    return shapes


def lidar_points(data, limit=1800):
    """Sample XYZ from UeSim ROS2 PointCloud2 CDR without NumPy/OpenCV."""
    if data[:4] != b'\x00\x01\x00\x00':
        raise ValueError('仅支持小端 XCDR1 PointCloud2')
    offset = 4

    def number(fmt='I'):
        nonlocal offset
        alignment = 1 if fmt == 'B' else 4
        offset = (offset + alignment - 1) // alignment * alignment
        value = struct.unpack_from('<' + fmt, data, offset)[0]
        offset += struct.calcsize(fmt)
        return value

    def string():
        nonlocal offset
        length = number()
        if length < 1 or offset + length > len(data):
            raise ValueError('无效的 CDR 字符串')
        value = data[offset:offset + length - 1].decode('utf-8')
        offset += length
        return value

    number('i')  # Header.sec remains unchanged in the recorded payload.
    if number() >= 1000000000:
        raise ValueError('无效的纳秒时间戳')
    frame_id = string()
    height, width, field_count = number(), number(), number()
    if height * width > 100000000 or not 1 <= field_count <= 128:
        raise ValueError('无效的点云维度或字段数量')
    fields = {}
    for _ in range(field_count):
        name = string()
        fields[name] = (number(), number('B'), number())
    endian = '>' if number('B') else '<'
    point_step, row_step, payload_size = number(), number(), number()
    if point_step <= 0 or row_step < width * point_step or payload_size < row_step * height or offset + payload_size > len(data):
        raise ValueError('点云数据长度或步长错误')
    xyz = []
    for name in ('x', 'y', 'z'):
        field = fields.get(name)
        if field is None or field[1] not in (7, 8) or field[2] < 1:
            raise ValueError('点云缺少浮点 XYZ 字段')
        field_offset, datatype, _ = field
        fmt = 'f' if datatype == 7 else 'd'
        if field_offset + struct.calcsize(fmt) > point_step:
            raise ValueError('点云字段越界')
        xyz.append((field_offset, endian + fmt))
    count = height * width
    points = []
    for index in range(0, count, max(1, math.ceil(count / limit))):
        row, col = divmod(index, width)
        base = offset + row * row_step + col * point_step
        point = tuple(struct.unpack_from(fmt, data, base + delta)[0] for delta, fmt in xyz)
        if all(math.isfinite(value) for value in point):
            points.append(point[:2])
    return points, count, frame_id


def decode_preview(payload, encoding, size):
    """Select a renderer from message contents, independent of topic names."""
    try:
        encoded, _ = compressed_image(payload)
    except (ValueError, UnicodeError, struct.error):
        encoded = b''
    if encoded.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n')):
        try:
            picture, dimensions, frame = camera_preview(payload, size)
            return 'image', f'图像 · {dimensions[0]}×{dimensions[1]} · frame={frame}', picture
        except ImportError:
            return 'text', '图像预览需要 Pillow：python -m pip install Pillow', None
        except (OSError, ValueError) as exc:
            return 'text', f'图像数据损坏：{exc}', None
    if payload[:4] == b'\x00\x01\x00\x00':
        try:
            points, count, frame = lidar_points(payload)
            return 'lidar', f'PointCloud2 · {count:,} 点 · frame={frame}', points
        except (ValueError, UnicodeError, struct.error):
            pass
    try:
        text = payload.decode('utf-8').strip('\x00 \r\n\t')
        if not all(char.isprintable() or char in '\n\r\t' for char in text):
            raise ValueError('binary payload')
        try:
            obj = json.loads(text)
        except ValueError:
            return 'text', f'文本 · {encoding}\n{text[:3000]}', None
        shapes = bbox_shapes(payload, include_metadata=True)
        if shapes:
            return 'bbox', f'BBox · {len(shapes)} 个目标', shapes
        formatted = json.dumps(obj, ensure_ascii=False, indent=2)
        return 'text', f'JSON · {encoding}\n{formatted[:3000]}', None
    except (UnicodeError, ValueError, RecursionError):
        return 'text', (f'未识别的二进制格式 · {encoding} · {len(payload):,} 字节\n'
                        f'前 64 字节（十六进制）：\n{payload[:64].hex(" ")}'), None


class App:
    def __init__(self, root, endpoint):
        self.root = root
        root.title('UeSim · BBox / 激光雷达 / 图像录制与回放')
        root.geometry('1120x800')
        root.minsize(1000, 740)
        self.lock = threading.Lock()
        self.events = queue.Queue()
        self.preview_jobs = queue.Queue(maxsize=1)
        self.preview_results = queue.Queue(maxsize=1)
        self.preview_stop = threading.Event()
        self.latest = {}
        self.stats = {}
        self.started = time.monotonic()
        self.session = None
        self.subscribers = []
        self.recorder = None
        self.player = None
        self.replay_session = None
        self.loaded = None
        self.duration = 0.0
        self.busy = False
        self.closing = False
        self.last_preview = 0.0
        self.preview_version = 0
        self.endpoint = tk.StringVar(value=endpoint)
        self.topics = tk.StringVar(value=', '.join(default_topics()))
        self.scan_expression = tk.StringVar(value='**')
        self.scan_duration = tk.StringVar(value='3')
        self.file = tk.StringVar()
        self.status = tk.StringVar(value='就绪：开始读取可预览数据；开始录制会同时启动读取。')
        self.speed = tk.StringVar(value='1')
        self.republish = tk.BooleanVar(value=False)
        self.preview_topics = [tk.StringVar(), tk.StringVar()]
        self.preview_boxes = []
        self.preview_canvases = []
        self.preview_photos = [None, None]
        self.available_topics = []
        self.loaded_topics = []
        self.range = tk.StringVar(value='60')
        self.progress_text = tk.StringVar(value='尚未打开录制文件')
        self.record_text = tk.StringVar(value='未录制')
        self._build()
        self.preview_thread = threading.Thread(target=self._decode_preview, daemon=True)
        self.preview_thread.start()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.poll)

    def _build(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill='both', expand=True)
        connection = ttk.LabelFrame(outer, text='实时数据', padding=8)
        connection.pack(fill='x')
        ttk.Label(connection, text='Zenoh 地址').grid(row=0, column=0, sticky='w')
        self.endpoint_entry = ttk.Entry(connection, textvariable=self.endpoint, width=35)
        self.endpoint_entry.grid(row=0, column=1, sticky='ew', padx=8)
        ttk.Label(connection, text='订阅主题（逗号分隔，可填写多个雷达）').grid(row=1, column=0, sticky='w')
        self.topics_entry = ttk.Entry(connection, textvariable=self.topics)
        self.topics_entry.grid(row=1, column=1, columnspan=3, sticky='ew', padx=8, pady=6)
        connection.columnconfigure(1, weight=1)
        self.read_button = ttk.Button(connection, text='开始读取', command=self.start_read)
        self.read_button.grid(row=0, column=2, padx=4)
        self.stop_read_button = ttk.Button(connection, text='停止读取', command=self.stop_read)
        self.stop_read_button.grid(row=0, column=3)
        discovery = ttk.Frame(connection)
        discovery.grid(row=2, column=0, columnspan=4, sticky='ew')
        ttk.Label(discovery, text='检测范围').pack(side='left')
        self.scan_entry = ttk.Entry(discovery, textvariable=self.scan_expression, width=24)
        self.scan_entry.pack(side='left', padx=8)
        ttk.Label(discovery, text='检测时长（秒）').pack(side='left')
        self.scan_seconds = ttk.Entry(discovery, textvariable=self.scan_duration, width=6)
        self.scan_seconds.pack(side='left', padx=8)
        self.detect_button = ttk.Button(discovery, text='检测并选择 Topic…', command=self.start_detection)
        self.detect_button.pack(side='left', padx=8)
        ttk.Label(discovery, text='仅检测正在发布的主题；请先启动仿真').pack(side='left')
        recording = ttk.LabelFrame(outer, text='录制原始数据', padding=8)
        recording.pack(fill='x', pady=8)
        self.record_button = ttk.Button(recording, text='开始录制…', command=self.start_record)
        self.record_button.pack(side='left')
        self.stop_record_button = ttk.Button(recording, text='结束录制', command=self.stop_record)
        self.stop_record_button.pack(side='left', padx=8)
        ttk.Label(recording, textvariable=self.record_text).pack(side='left')
        replay = ttk.LabelFrame(outer, text='文件回放', padding=8)
        replay.pack(fill='x')
        self.open_button = ttk.Button(replay, text='打开录制文件…', command=self.open_file)
        self.open_button.grid(row=0, column=0)
        ttk.Entry(replay, textvariable=self.file, state='readonly').grid(row=0, column=1, columnspan=5, sticky='ew', padx=8)
        replay.columnconfigure(1, weight=1)
        self.play_button = ttk.Button(replay, text='播放', command=self.play)
        self.play_button.grid(row=1, column=0, pady=8)
        self.pause_button = ttk.Button(replay, text='暂停', command=self.pause)
        self.pause_button.grid(row=1, column=1, sticky='w', padx=8)
        self.stop_play_button = ttk.Button(replay, text='停止播放', command=self.stop_play)
        self.stop_play_button.grid(row=1, column=2, padx=8)
        ttk.Label(replay, text='倍速').grid(row=1, column=3)
        self.speed_box = ttk.Combobox(replay, textvariable=self.speed, values=('0.25', '0.5', '1', '2', '4'), width=6, state='readonly')
        self.speed_box.grid(row=1, column=4, padx=8)
        self.republish_check = ttk.Checkbutton(replay, text='重新发布到原 Zenoh 主题', variable=self.republish)
        self.republish_check.grid(row=1, column=5)
        self.progress = ttk.Progressbar(replay, maximum=1)
        self.progress.grid(row=2, column=0, columnspan=6, sticky='ew')
        ttk.Label(replay, textvariable=self.progress_text).grid(row=3, column=0, columnspan=6, sticky='w')
        preview = ttk.LabelFrame(outer, text='数据预览（文件保留完整原始数据）', padding=6)
        preview.pack(fill='both', expand=True, pady=8)
        toolbar = ttk.Frame(preview)
        toolbar.pack(fill='x')
        ttk.Label(toolbar, text='点云显示半径（米）').pack(side='left')
        ttk.Entry(toolbar, textvariable=self.range, width=7).pack(side='left', padx=8)
        ttk.Label(toolbar, text='自动识别消息格式；两个窗口可独立选择同一或不同 Topic').pack(side='left')
        views = ttk.Frame(preview)
        views.pack(fill='both', expand=True)
        for index, topic in enumerate(self.preview_topics):
            pane = ttk.Frame(views, padding=4)
            pane.grid(row=0, column=index, sticky='nsew')
            views.columnconfigure(index, weight=1, uniform='preview')
            ttk.Label(pane, text=f'预览 {index + 1} · Topic').pack(anchor='w')
            box = ttk.Combobox(pane, textvariable=topic, state='readonly')
            box.pack(fill='x', pady=(3, 6))
            box.bind('<<ComboboxSelected>>', lambda event, i=index: self.clear_preview(i))
            canvas = tk.Canvas(pane, background='#10202d', highlightthickness=0, height=160, width=300)
            canvas.pack(fill='both', expand=True)
            self.preview_boxes.append(box)
            self.preview_canvases.append(canvas)
        views.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(outer, columns=('topic', 'count', 'size', 'rate'), show='headings', height=3)
        for key, label, width in [('topic', '主题', 440), ('count', '消息数', 100), ('size', '数据量 MiB', 120), ('rate', '平均 Hz', 100)]:
            self.table.heading(key, text=label)
            self.table.column(key, width=width)
        self.table.pack(fill='x')
        ttk.Label(outer, textvariable=self.status, wraplength=1050).pack(fill='x', pady=(8, 0))
        self.controls()

    def controls(self):
        live, recording, playing = self.session is not None, self.recorder is not None, self.player is not None
        rules = [(self.read_button, not live and not playing), (self.stop_read_button, live),
                 (self.detect_button, not live and not playing),
                 (self.record_button, not recording and not playing), (self.stop_record_button, recording),
                 (self.open_button, not live and not playing), (self.play_button, self.loaded is not None and not live and not playing),
                 (self.pause_button, playing), (self.stop_play_button, playing)]
        for widget, enabled in rules:
            widget.configure(state='normal' if enabled and not self.busy else 'disabled')
        self.speed_box.configure(state='readonly' if not playing and not self.busy else 'disabled')
        self.republish_check.configure(state='normal' if not playing and not self.busy else 'disabled')
        for widget in (self.endpoint_entry, self.topics_entry, self.scan_entry, self.scan_seconds):
            widget.configure(state='disabled' if live or playing or self.busy else 'normal')

    def start_detection(self):
        endpoint = self.endpoint.get().strip()
        expression = self.scan_expression.get().strip()
        try:
            duration = float(self.scan_duration.get())
            if not endpoint or not expression:
                raise ValueError('请填写 Zenoh 地址和检测范围（例如 ** 或 rt/**）')
            if not math.isfinite(duration) or not 0.5 <= duration <= 60:
                raise ValueError('检测时长应在 0.5 到 60 秒之间')
        except ValueError as exc:
            messagebox.showerror('配置错误', str(exc))
            return
        self.work(f'正在检测 {expression}，监听 {duration:g} 秒…',
                  lambda: detect_topics(endpoint, expression, duration), self.choose_topics)

    def choose_topics(self, stats):
        self.status.set(f'检测完成：发现 {len(stats)} 个活跃主题。')
        if not stats:
            messagebox.showinfo('未检测到 Topic',
                '检测期间未收到消息。请检查 Zenoh 地址、检测范围和仿真发布状态，或增加检测时长。\n'
                '也可以在订阅主题输入框中手动填写。')
            return
        dialog = tk.Toplevel(self.root)
        dialog.title('选择要读取和录制的 Topic')
        dialog.geometry('800x440')
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text='按 Ctrl / Shift 可多选；应用后点击“开始录制”。未选主题不会订阅或录制。',
                  padding=10).pack(fill='x')
        frame = ttk.Frame(dialog, padding=(10, 0))
        frame.pack(fill='both', expand=True)
        table = ttk.Treeview(frame, columns=('topic', 'count', 'size'), show='headings', selectmode='extended')
        for key, label, width in [('topic', 'Topic', 510), ('count', '检测消息数', 100), ('size', '数据量 MiB', 120)]:
            table.heading(key, text=label)
            table.column(key, width=width)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        table.pack(fill='both', expand=True)
        configured = {t.strip() for t in self.topics.get().split(',') if t.strip()}
        for topic, (count, size) in stats.items():
            row = table.insert('', 'end', values=(topic, count, f'{size / 1048576:.2f}'))
            if topic in configured:
                table.selection_add(row)
        actions = ttk.Frame(dialog, padding=10)
        actions.pack(fill='x')
        ttk.Button(actions, text='全选', command=lambda: table.selection_set(table.get_children())).pack(side='left')
        ttk.Button(actions, text='清空选择', command=lambda: table.selection_remove(table.selection())).pack(side='left', padx=8)

        def apply():
            selected = [str(table.item(row, 'values')[0]) for row in table.selection()]
            if not selected:
                messagebox.showwarning('尚未选择', '请至少选择一个 Topic。', parent=dialog)
                return
            self.topics.set(', '.join(selected))
            self.status.set(f'已选择 {len(selected)} 个主题，点击“开始录制”保存所选数据。')
            dialog.destroy()

        ttk.Button(actions, text='应用选择', command=apply).pack(side='right')
        ttk.Button(actions, text='取消', command=dialog.destroy).pack(side='right', padx=8)

    def work(self, label, operation, done=None):
        self.busy = True
        self.status.set(label)
        self.controls()
        def run():
            try:
                result = operation()
                self.events.put((done, result, None))
            except Exception as exc:
                self.events.put((None, None, str(exc)))
        threading.Thread(target=run, daemon=True).start()

    def reset_view(self, topics=()):
        with self.lock:
            self.latest.clear()
            self.stats.clear()
            self.started = time.monotonic()
            self.preview_version += 1
        for row in self.table.get_children():
            self.table.delete(row)
        self.available_topics = list(topics)
        for topic in self.preview_topics:
            topic.set('')
        self.update_preview_topics()

    def clear_preview(self, index):
        self.preview_photos[index] = None
        canvas = self.preview_canvases[index]
        canvas.delete('all')
        canvas.create_text(10, 12, text='等待所选 Topic 数据', fill='white', anchor='nw')
        self.last_preview = 0

    def update_preview_topics(self):
        for index, (topic, box) in enumerate(zip(self.preview_topics, self.preview_boxes)):
            box.configure(values=self.available_topics)
            if topic.get() not in self.available_topics:
                topic.set(self.available_topics[min(index, len(self.available_topics) - 1)] if self.available_topics else '')
                self.clear_preview(index)

    def receive(self, topic, payload, encoding):
        with self.lock:
            self.latest[topic] = (payload, encoding)
            count, size = self.stats.get(topic, (0, 0))
            self.stats[topic] = (count + 1, size + len(payload))
            if self.recorder is not None:
                self.recorder.submit(topic, payload, encoding)

    def connect(self, endpoint, topics):
        session = open_session(endpoint)
        subscribers = []
        try:
            for topic in topics:
                subscribers.append(session.declare_subscriber(topic,
                    lambda sample: self.receive(str(sample.key_expr), bytes(sample.payload), str(sample.encoding))))
        except Exception:
            session.close()
            raise
        self.session, self.subscribers = session, subscribers

    def settings(self):
        topics = list(dict.fromkeys(t.strip() for t in self.topics.get().split(',') if t.strip()))
        endpoint = self.endpoint.get().strip()
        if not endpoint or not topics:
            raise ValueError('请填写 Zenoh 地址和至少一个订阅主题')
        return endpoint, topics

    def start_read(self):
        try:
            endpoint, topics = self.settings()
        except ValueError as exc:
            messagebox.showerror('配置错误', str(exc))
            return
        self.reset_view(topics)
        self.work('正在连接 Zenoh…', lambda: self.connect(endpoint, topics),
                  lambda _: self.status.set('正在读取；点击“开始录制”保存数据。'))

    def detach_recorder(self):
        with self.lock:
            recorder, self.recorder = self.recorder, None
        if recorder:
            recorder.stop()
        return recorder

    def disconnect(self):
        try:
            self.detach_recorder()
        finally:
            if self.session:
                self.session.close()
                self.session = None
                self.subscribers = []

    def stop_read(self):
        self.work('正在停止读取并保存录制文件…', self.disconnect,
                  lambda _: (self.status.set('已停止读取，录制数据已保存。'), self.record_text.set('未录制')))

    def start_record(self):
        try:
            endpoint, topics = self.settings()
        except ValueError as exc:
            messagebox.showerror('配置错误', str(exc))
            return
        path = filedialog.asksaveasfilename(title='保存新的录制文件（不能覆盖已有文件）',
            initialfile=datetime.now().strftime('bbox_lidar_%Y%m%d_%H%M%S.uesimrec'),
            defaultextension='.uesimrec', filetypes=[('UeSim 录制', '*.uesimrec')])
        if not path:
            return
        if Path(path).exists():
            messagebox.showerror('文件已存在', '请选择新的文件名，避免覆盖已有录制。')
            return
        if not self.session:
            self.reset_view(topics)
        def begin():
            if not self.session:
                self.connect(endpoint, topics)
            recorder = Recorder(path, topics)
            with self.lock:
                self.recorder = recorder
        self.work('正在开始录制…', begin, lambda _: self.status.set(f'正在录制：{path}'))

    def stop_record(self):
        def finished(recorder):
            self.record_text.set(f'已保存 {recorder.count:,} 条消息')
            self.status.set(f'录制完成：{recorder.path}；实时读取继续。')
        self.work('正在写完队列并保存文件…', self.detach_recorder, finished)

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[('UeSim 录制', '*.uesimrec'), ('所有文件', '*')])
        if not path:
            return
        def loaded(result):
            meta, rows, self.duration = result
            self.loaded = path
            self.file.set(path)
            self.progress.configure(maximum=max(self.duration, 0.001))
            self.progress['value'] = 0
            self.progress_text.set(f'{self.duration:.2f} 秒 · {sum(r[1] for r in rows):,} 条消息 · {len(rows)} 个主题')
            self.status.set('文件已打开，可离线播放。' if meta.get('complete') == 'true' else
                            '此文件未正常结束或曾丢帧；可回放已保存的数据。')
            self.loaded_topics = [row[0] for row in rows]
            self.reset_view(self.loaded_topics)
            for row in self.table.get_children():
                self.table.delete(row)
            for topic, count, size in rows:
                self.table.insert('', 'end', values=(topic, count, f'{size / 1048576:.2f}', '—'))
        self.work('正在读取文件信息…', lambda: inspect_recording(path), loaded)

    def play(self):
        path, speed = self.loaded, float(self.speed.get())
        republish, endpoint = self.republish.get(), self.endpoint.get().strip()
        self.reset_view(self.loaded_topics)
        def begin():
            session = open_session(endpoint) if republish else None
            try:
                self.player = Player(path, self.receive, speed, session)
                self.replay_session = session
                self.player.start()
            except Exception:
                if session:
                    session.close()
                self.player = None
                self.replay_session = None
                raise
        self.work('正在启动播放…', begin, lambda _: self.status.set(
            '正在播放并发布到原主题；请停止仿真端同主题发布，避免数据混合。' if republish else '正在离线播放。'))

    def pause(self):
        self.player.pause(not self.player.paused)
        self.pause_button.configure(text='继续' if self.player.paused else '暂停')
        self.status.set('播放已暂停。' if self.player.paused else '正在播放。')

    def end_player(self):
        player, self.player = self.player, None
        if player:
            player.stop()
        if self.replay_session:
            self.replay_session.close()
            self.replay_session = None
        if player and player.error:
            raise RuntimeError(player.error)

    def stop_play(self):
        self.work('正在停止播放…', self.end_player, lambda _: self.status.set('播放已停止；再次播放从头开始。'))
        self.pause_button.configure(text='暂停')

    def _decode_preview(self):
        while not self.preview_stop.is_set():
            try:
                version, jobs = self.preview_jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            results = []
            for topic, packet, size in jobs:
                try:
                    result = decode_preview(*packet, size) if packet else ('text', '等待所选 Topic 数据', None)
                except Exception as exc:
                    result = ('text', f'预览失败：{exc}', None)
                results.append((topic, result))
            try:
                self.preview_results.get_nowait()
            except queue.Empty:
                pass
            self.preview_results.put((version, results))

    def draw(self, canvas, shapes, points, caption, radius=None):
        canvas.delete('all')
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if radius is None:
            coords = [p for record in shapes for p in record[1]]
            xs, ys = [p[0] for p in coords], [p[1] for p in coords]
            cx = (min(xs) + max(xs)) / 2 if xs else 0
            cy = (min(ys) + max(ys)) / 2 if ys else 0
            radius = max(10, max((abs(x - cx) for x in xs), default=0), max((abs(y - cy) for y in ys), default=0)) * 1.15
        else:
            cx, cy = 0, 0
        scale = max(1, min(w - 40, h - 55)) / (2 * radius)
        def pixel(x, y):
            return w / 2 + (x - cx) * scale, h / 2 - (y - cy) * scale
        ox, oy = pixel(0, 0)
        canvas.create_line(0, oy, w, oy, fill='#345063')
        canvas.create_line(ox, 0, ox, h, fill='#345063')
        for record in shapes[:500]:
            label, shape = record[:2]
            category, velocity, speed = record[2:] if len(record) > 2 else ('unknown', None, None)
            from bbox_motion import speed_label
            color = {'vehicle': '#58a6ff', 'human': '#f2ba57'}.get(category, '#a4b9ca')
            coords = [v for p in shape for v in pixel(*p)]
            canvas.create_polygon(*coords, outline=color, fill='', width=2)
            canvas.create_text(coords[0], coords[1] - 7, text=f'{label[:24]} · {category} · {speed_label(speed)}', fill=color, font=('', 9))
            if velocity is not None and math.hypot(*velocity[:2]) > .01:
                x, y = (sum(p[i] for p in shape) / len(shape) for i in (0, 1))
                canvas.create_line(*pixel(x, y), *pixel(x + velocity[0], y + velocity[1]), fill='#65ddc7', width=2, arrow=tk.LAST)
        for x, y in points:
            if math.isfinite(x) and math.isfinite(y) and abs(x) <= radius and abs(y) <= radius:
                px, py = pixel(x, y)
                canvas.create_rectangle(px, py, px + 2, py + 2, outline='', fill='#65ddc7')
        canvas.create_text(10, 12, text=caption, fill='white', anchor='nw', width=max(100, w - 20))
        canvas.create_text(10, h - 12, text=f'X → / Y ↑ · 显示半宽 {radius:g} m', fill='#a4b9ca', anchor='sw')

    def poll(self):
        try:
            while True:
                done, result, error = self.events.get_nowait()
                self.busy = False
                if error:
                    self.status.set(error)
                    if not self.closing:
                        messagebox.showerror('操作失败', error)
                elif done:
                    done(result)
                if self.closing:
                    self.root.destroy()
                    return
                self.controls()
        except queue.Empty:
            pass
        player = self.player
        if player:
            self.progress['value'] = player.position
            self.progress_text.set(f'{player.position:.2f} / {self.duration:.2f} 秒 · 已播放 {player.count:,} 条')
            if player.done.is_set() and not self.busy:
                self.work('正在结束播放…', self.end_player, lambda _: self.status.set('播放完成。'))
                self.pause_button.configure(text='暂停')
        recorder = self.recorder
        if recorder:
            self.record_text.set(f'{recorder.count:,} 条 · {recorder.bytes / 1048576:.1f} MiB · 排队 {recorder.queued_bytes / 1048576:.1f} MiB')
            if recorder.error and not self.busy:
                self.stop_record()
        with self.lock:
            latest, stats = dict(self.latest), dict(self.stats)
            elapsed = max(0.01, time.monotonic() - self.started)
        if stats:
            for row in self.table.get_children():
                self.table.delete(row)
            for topic, (count, size) in sorted(stats.items()):
                self.table.insert('', 'end', values=(topic, count, f'{size / 1048576:.2f}', f'{count / elapsed:.1f}'))
        for topic in latest:
            if topic not in self.available_topics:
                self.available_topics.append(topic)
        self.update_preview_topics()
        if time.monotonic() - self.last_preview > 0.25:
            try:
                jobs = [(topic.get(), latest.get(topic.get()),
                         (max(1, canvas.winfo_width() - 16), max(1, canvas.winfo_height() - 85)))
                        for topic, canvas in zip(self.preview_topics, self.preview_canvases)]
                self.preview_jobs.put_nowait((self.preview_version, jobs))
                self.last_preview = time.monotonic()
            except queue.Full:
                pass
        try:
            version, results = self.preview_results.get_nowait()
            if version == self.preview_version:
                for index, (topic, result) in enumerate(results):
                    if topic != self.preview_topics[index].get():
                        continue
                    kind, caption, data = result
                    canvas = self.preview_canvases[index]
                    self.preview_photos[index] = None
                    caption = f'{topic} · {caption}' if topic else caption
                    if kind == 'bbox':
                        self.draw(canvas, data, [], caption)
                    elif kind == 'lidar':
                        try:
                            radius = float(self.range.get())
                            if not math.isfinite(radius) or not 0.1 <= radius <= 100000:
                                radius = 60
                        except ValueError:
                            radius = 60
                        self.draw(canvas, [], data, caption, radius)
                    else:
                        canvas.delete('all')
                        w, h = canvas.winfo_width(), canvas.winfo_height()
                        if kind == 'image':
                            from PIL import ImageTk
                            self.preview_photos[index] = ImageTk.PhotoImage(data, master=self.root)
                            canvas.create_image(w / 2, (h + 70) / 2, image=self.preview_photos[index])
                        canvas.create_text(10, 12, text=caption, fill='white', anchor='nw', width=max(100, w - 20))
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            self.status.set('正在完成当前操作，请稍后关闭。')
            return
        self.closing = True
        self.preview_stop.set()
        def shutdown():
            try:
                self.disconnect()
            finally:
                self.end_player()
        self.work('正在保存并退出…', shutdown)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connect', default='tcp/127.0.0.1:7447')
    args = parser.parse_args()
    root = tk.Tk()
    App(root, args.connect)
    root.mainloop()


if __name__ == '__main__':
    main()
