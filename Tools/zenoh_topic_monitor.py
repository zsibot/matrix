#!/usr/bin/env python3
"""
Monitor live Zenoh topics, message rate, payload size, and timestamp latency.

Examples:
  python zenoh_topic_monitor.py --mode client --connect tcp/127.0.0.1:7447

Notes:
  Zenoh does not have a ROS-like topic graph in this simple subscriber path.
  This script "discovers" topics when matching samples are received.
"""

from __future__ import annotations

import argparse
import json
import math
import signal
import struct
import sys
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

import zenoh


@dataclass
class TopicStats:
    total: int = 0
    window_times: Deque[float] = field(default_factory=deque)
    last_recv: float = 0.0
    last_size: int = 0
    last_latency_ms: Optional[float] = None
    latency_min_ms: Optional[float] = None
    latency_max_ms: Optional[float] = None
    latency_sum_ms: float = 0.0
    latency_count: int = 0

    def add_latency(self, latency_ms: Optional[float]) -> None:
        self.last_latency_ms = latency_ms
        if latency_ms is None:
            return
        self.latency_count += 1
        self.latency_sum_ms += latency_ms
        self.latency_min_ms = latency_ms if self.latency_min_ms is None else min(self.latency_min_ms, latency_ms)
        self.latency_max_ms = latency_ms if self.latency_max_ms is None else max(self.latency_max_ms, latency_ms)

    @property
    def latency_avg_ms(self) -> Optional[float]:
        if self.latency_count == 0:
            return None
        return self.latency_sum_ms / self.latency_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan Zenoh topics and print rate/latency statistics.")
    parser.add_argument("--key", default="**", help="Zenoh key expression to subscribe to, default: **")
    parser.add_argument("--mode", choices=("router", "client", "peer"), default="client", help="Zenoh session mode.")
    parser.add_argument("--connect", action="append", default=["tcp/127.0.0.1:7447"], help="Router endpoint to connect to. Can repeat.")
    parser.add_argument("--listen", action="append", default=[], help="Endpoint to listen on. Can repeat.")
    parser.add_argument("--interval", type=float, default=1.0, help="Print interval in seconds.")
    parser.add_argument("--window", type=float, default=5.0, help="Sliding window for Hz calculation in seconds.")
    parser.add_argument("--max-topics", type=int, default=50, help="Maximum number of topics to show.")
    parser.add_argument("--sort", choices=("hz", "name", "last"), default="hz", help="Sort table by this field.")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear the console between refreshes.")
    parser.add_argument("--show-empty", action="store_true", help="Keep topics visible even if no samples in the window.")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> "zenoh.Config":
    conf = zenoh.Config()
    conf.insert_json5("mode", json.dumps(args.mode))

    connect = args.connect
    listen = args.listen
    if not connect and not listen:
        if args.mode == "router":
            listen = ["tcp/0.0.0.0:7447"]
        elif args.mode == "client":
            connect = ["tcp/127.0.0.1:7447"]

    if connect:
        conf.insert_json5("connect/endpoints", json.dumps(connect))
    if listen:
        conf.insert_json5("listen/endpoints", json.dumps(listen))

    # Keep startup deterministic on machines with several NICs/WSL adapters.
    if connect or listen:
        conf.insert_json5("scouting/multicast/enabled", "false")

    return conf


def bytes_from_payload(payload) -> bytes:
    try:
        return bytes(payload)
    except TypeError:
        return payload.to_bytes()


def sane_epoch(seconds: float, now: float) -> bool:
    if not math.isfinite(seconds):
        return False
    # Accept timestamps from 2020-01-01 to 10 minutes in the future.
    return 1_577_836_800 <= seconds <= now + 600


def latency_from_ros2_cdr(data: bytes, now: float) -> Optional[float]:
    if len(data) < 12:
        return None
    if data[:4] not in (b"\x00\x01\x00\x00", b"\x00\x00\x00\x00"):
        return None

    # Most ROS2 XCDR1 little-endian payloads start with:
    # encapsulation(4), stamp.sec(int32/uint32), stamp.nanosec(uint32).
    sec, nanosec = struct.unpack_from("<II", data, 4)
    stamp = float(sec) + float(nanosec) / 1_000_000_000.0
    if sane_epoch(stamp, now):
        return (now - stamp) * 1000.0
    return None


def latency_from_json_or_text(data: bytes, now: float) -> Optional[float]:
    text = data[:4096].decode("utf-8", errors="ignore").strip()
    if not text:
        return None

    # Plain epoch timestamp in seconds or milliseconds.
    try:
        value = float(text)
        if value > 10_000_000_000:
            value /= 1000.0
        if sane_epoch(value, now):
            return (now - value) * 1000.0
    except ValueError:
        pass

    if not (text.startswith("{") and text.endswith("}")):
        return None

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None

    candidates = [
        obj.get("timestamp"),
        obj.get("time"),
        obj.get("stamp"),
        obj.get("ts"),
    ]

    header = obj.get("header")
    if isinstance(header, dict):
        candidates.append(header.get("stamp"))

    for candidate in candidates:
        stamp = normalize_stamp(candidate)
        if stamp is not None and sane_epoch(stamp, now):
            return (now - stamp) * 1000.0

    return None


def normalize_stamp(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        return seconds / 1000.0 if seconds > 10_000_000_000 else seconds
    if isinstance(value, str):
        try:
            seconds = float(value)
            return seconds / 1000.0 if seconds > 10_000_000_000 else seconds
        except ValueError:
            return None
    if isinstance(value, dict):
        sec = value.get("sec", value.get("secs", value.get("seconds")))
        nsec = value.get("nanosec", value.get("nsec", value.get("nanoseconds", 0)))
        if sec is None:
            return None
        try:
            return float(sec) + float(nsec) / 1_000_000_000.0
        except (TypeError, ValueError):
            return None
    return None


def extract_latency_ms(data: bytes, now: float) -> Optional[float]:
    return latency_from_ros2_cdr(data, now) or latency_from_json_or_text(data, now)


def format_ms(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:8.2f}"


def format_age(value: float, now: float) -> str:
    if value <= 0:
        return "n/a"
    return f"{now - value:6.2f}s"


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def main() -> int:
    args = parse_args()
    stats: Dict[str, TopicStats] = defaultdict(TopicStats)
    lock = threading.Lock()
    stop_event = threading.Event()

    def handle_signal(signum, frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    conf = build_config(args)
    session = zenoh.open(conf)

    def listener(sample) -> None:
        now = time.time()
        key = str(sample.key_expr)
        data = bytes_from_payload(sample.payload)
        latency_ms = extract_latency_ms(data, now)

        with lock:
            item = stats[key]
            item.total += 1
            item.last_recv = now
            item.last_size = len(data)
            item.window_times.append(now)
            cutoff = now - args.window
            while item.window_times and item.window_times[0] < cutoff:
                item.window_times.popleft()
            item.add_latency(latency_ms)

    sub = session.declare_subscriber(args.key, listener)

    try:
        while not stop_event.wait(args.interval):
            now = time.time()
            cutoff = now - args.window
            rows = []
            with lock:
                for key, item in stats.items():
                    while item.window_times and item.window_times[0] < cutoff:
                        item.window_times.popleft()
                    hz = len(item.window_times) / max(args.window, 0.001)
                    if not args.show_empty and hz <= 0:
                        continue
                    rows.append((key, item, hz))

            if args.sort == "name":
                rows.sort(key=lambda row: row[0])
            elif args.sort == "last":
                rows.sort(key=lambda row: row[1].last_recv, reverse=True)
            else:
                rows.sort(key=lambda row: row[2], reverse=True)

            if not args.no_clear:
                clear_screen()

            print(f"Zenoh monitor | key={args.key} | topics={len(stats)} | window={args.window:.1f}s")
            print(f"{'topic':58} {'hz':>8} {'count':>9} {'size':>8} {'age':>8} {'last_ms':>10} {'avg_ms':>10} {'min_ms':>10} {'max_ms':>10}")
            print("-" * 137)
            for key, item, hz in rows[: args.max_topics]:
                short_key = key if len(key) <= 58 else "..." + key[-55:]
                print(
                    f"{short_key:58} "
                    f"{hz:8.2f} "
                    f"{item.total:9d} "
                    f"{item.last_size:8d} "
                    f"{format_age(item.last_recv, now):>8} "
                    f"{format_ms(item.last_latency_ms):>10} "
                    f"{format_ms(item.latency_avg_ms):>10} "
                    f"{format_ms(item.latency_min_ms):>10} "
                    f"{format_ms(item.latency_max_ms):>10}"
                )
            sys.stdout.flush()
    finally:
        sub.undeclare()
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
