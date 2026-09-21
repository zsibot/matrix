#!/usr/bin/env python3
"""Display multiple UeSim bbox messages as a fixed-size 2D Zenoh view.

By default this subscribes to ``rt/dynamicinfo`` and draws a top-down XY view.
It accepts the project's actual double-encoded format, where the root object is
keyed by Actor name and every value is a JSON string, for example::

    {"BP_Simple_Sedan26": "{\"center\":...,\"corners\":[...]}"}

JSON arrays and ``{"bboxes": [...]}`` wrappers are also supported. Input bbox
values are already in the ROS X-forward/Y-left/Z-up frame and in metres. Each
target is drawn as an oriented XY rectangle with a forward arrow.

Install and run:

    python3 -m pip install eclipse-zenoh matplotlib

    # MATRiX release package
    python3 Tools/visualize_zenoh_bbox_2d.py

    # UeSim source tree
    python3 Tools/visualize_zenoh_bbox_2d.py

The script is self-contained and does not import any other UeSim/MATRiX file.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import zenoh
except ImportError:
    zenoh = None

try:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    from matplotlib.patches import FancyArrowPatch, Polygon
except ImportError:
    plt = None
    FuncAnimation = None
    FancyArrowPatch = None
    Polygon = None


Point2 = Tuple[float, float]
Vec3 = Tuple[float, float, float]


@dataclass
class BBox:
    center: Vec3
    extent: Vec3
    size: Vec3
    rotation: Vec3  # pitch, yaw, roll in degrees
    forward: Vec3
    corners: List[Vec3]
    label: str


@dataclass
class LatestFrame:
    boxes: List[BBox]
    key: str
    sequence: int
    received_at: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Display multiple UeSim bboxes as rectangles in a fixed 2D metre view."
    )
    parser.add_argument(
        "--key",
        default="rt/dynamicinfo",
        help="Zenoh key expression (default: rt/dynamicinfo).",
    )
    parser.add_argument(
        "--mode",
        choices=("router", "client", "peer"),
        default="client",
        help="Zenoh session mode (default: client).",
    )
    parser.add_argument(
        "--connect",
        action="append",
        default=None,
        help=(
            "Endpoint to connect to; may be repeated "
            "(default for client: tcp/127.0.0.1:7447)."
        ),
    )
    parser.add_argument(
        "--listen",
        action="append",
        default=None,
        help="Endpoint to listen on; may be repeated.",
    )
    parser.add_argument(
        "--interval-ms",
        type=int,
        default=50,
        help="Plot refresh interval in milliseconds (default: 50).",
    )
    parser.add_argument(
        "--image-width",
        type=int,
        default=1280,
        help="Fixed image width in pixels (default: 1280).",
    )
    parser.add_argument(
        "--image-height",
        type=int,
        default=720,
        help="Fixed image height in pixels (default: 720).",
    )
    parser.add_argument("--dpi", type=int, default=100, help="Image DPI (default: 100).")
    parser.add_argument("--x-min", type=float, default=-250.0, help="Minimum world X in metres.")
    parser.add_argument("--x-max", type=float, default=150.0, help="Maximum world X in metres.")
    parser.add_argument("--y-min", type=float, default=-50.0, help="Minimum world Y in metres.")
    parser.add_argument("--y-max", type=float, default=50.0, help="Maximum world Y in metres.")
    return parser.parse_args()


def build_config(args: argparse.Namespace):
    """Build a Zenoh configuration without relying on a project helper module."""
    config = zenoh.Config()
    config.insert_json5("mode", json.dumps(args.mode))

    connect = list(args.connect or [])
    listen = list(args.listen or [])
    if not connect and not listen:
        if args.mode == "client":
            connect = ["tcp/127.0.0.1:7447"]
        elif args.mode == "router":
            listen = ["tcp/0.0.0.0:7447"]

    if connect:
        config.insert_json5("connect/endpoints", json.dumps(connect))
    if listen:
        config.insert_json5("listen/endpoints", json.dumps(listen))
    if connect or listen:
        config.insert_json5("scouting/multicast/enabled", "false")
    return config


def payload_to_bytes(payload: Any) -> bytes:
    try:
        return bytes(payload)
    except TypeError:
        return payload.to_bytes()


def decode_json_payload(payload: Any) -> Any:
    """Decode normal JSON and a JSON document encoded inside a JSON string."""
    text = payload_to_bytes(payload).decode("utf-8", errors="strict")
    text = text.strip("\x00 \t\r\n")
    value: Any = json.loads(text)
    if isinstance(value, str):
        value = json.loads(value)
    return value


def collect_bbox_objects(value: Any) -> List[Dict[str, Any]]:
    """Flatten supported bbox wrappers and Actor-keyed message objects."""
    if isinstance(value, str):
        try:
            return collect_bbox_objects(json.loads(value))
        except json.JSONDecodeError:
            return []

    if isinstance(value, list):
        result: List[Dict[str, Any]] = []
        for item in value:
            result.extend(collect_bbox_objects(item))
        return result
    if not isinstance(value, dict):
        return []

    if isinstance(value.get("center"), dict) and isinstance(value.get("extent"), dict):
        return [value]

    for wrapper_key in ("bboxes", "bbox", "objects", "actors", "dynamicinfo", "data"):
        if wrapper_key in value:
            wrapped = collect_bbox_objects(value[wrapper_key])
            if wrapped:
                return wrapped

    result = []
    for object_id, item in value.items():
        nested = collect_bbox_objects(item)
        for bbox in nested:
            if not any(key in bbox for key in ("label", "name", "id")):
                bbox = dict(bbox)
                bbox["label"] = str(object_id)
            result.append(bbox)
    return result


def finite_number(value: Any, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} is not finite")
    return number


def parse_vec3(value: Any, field_name: str, scale: float = 1.0) -> Vec3:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object with x/y/z")

    def component(name: str) -> float:
        raw = value.get(name, value.get(name.upper()))
        if raw is None:
            raise ValueError(f"{field_name}.{name} is missing")
        return finite_number(raw, f"{field_name}.{name}") * scale

    return component("x"), component("y"), component("z")


def parse_rotation(value: Any) -> Vec3:
    if not isinstance(value, dict):
        return 0.0, 0.0, 0.0

    def angle(name: str) -> float:
        raw = value.get(name, value.get(name.capitalize(), 0.0))
        return finite_number(raw, f"rotation.{name}")

    return angle("pitch"), angle("yaw"), angle("roll")


def parse_bbox(value: Dict[str, Any], index: int) -> BBox:
    center = parse_vec3(value.get("center"), "center")
    extent = parse_vec3(value.get("extent"), "extent")
    if isinstance(value.get("size"), dict):
        size = parse_vec3(value["size"], "size")
    else:
        size = tuple(component * 2.0 for component in extent)  # type: ignore[assignment]

    forward = parse_vec3(value.get("forward"), "forward")
    forward_length = math.sqrt(sum(component * component for component in forward))
    if forward_length > 1e-9:
        forward = tuple(component / forward_length for component in forward)  # type: ignore[assignment]

    raw_corners = value.get("corners")
    if not isinstance(raw_corners, list) or len(raw_corners) != 8:
        raise ValueError("corners must contain exactly 8 x/y/z objects")
    corners = [parse_vec3(corner, f"corners[{i}]") for i, corner in enumerate(raw_corners)]

    label_value = value.get("label", value.get("name", value.get("id", f"bbox {index}")))
    return BBox(
        center=center,
        extent=extent,
        size=size,
        rotation=parse_rotation(value.get("rotation")),
        forward=forward,
        corners=corners,
        label=str(label_value),
    )


def oriented_rectangle(box: BBox) -> List[Point2]:
    """Build a four-corner XY rectangle from center, extent and forward."""
    center_x, center_y = box.center[0], box.center[1]
    forward_x, forward_y = box.forward[0], box.forward[1]
    length = math.hypot(forward_x, forward_y)
    if length <= 1e-9:
        forward_x, forward_y = 1.0, 0.0
    else:
        forward_x /= length
        forward_y /= length

    # ROS local +Y is left when local +X is forward.
    left_x, left_y = -forward_y, forward_x
    half_length = abs(box.extent[0])
    half_width = abs(box.extent[1])
    return [
        (
            center_x - forward_x * half_length - left_x * half_width,
            center_y - forward_y * half_length - left_y * half_width,
        ),
        (
            center_x + forward_x * half_length - left_x * half_width,
            center_y + forward_y * half_length - left_y * half_width,
        ),
        (
            center_x + forward_x * half_length + left_x * half_width,
            center_y + forward_y * half_length + left_y * half_width,
        ),
        (
            center_x - forward_x * half_length + left_x * half_width,
            center_y - forward_y * half_length + left_y * half_width,
        ),
    ]


def main() -> int:
    args = parse_args()
    missing = []
    if zenoh is None:
        missing.append("eclipse-zenoh")
    if plt is None:
        missing.append("matplotlib")
    if missing:
        print(f"Missing dependencies. Install with: pip install {' '.join(missing)}", file=sys.stderr)
        return 2

    if args.image_width <= 0 or args.image_height <= 0 or args.dpi <= 0:
        print("Image width, height and DPI must be positive.", file=sys.stderr)
        return 2
    if args.x_min >= args.x_max or args.y_min >= args.y_max:
        print("World minimum bounds must be smaller than maximum bounds.", file=sys.stderr)
        return 2

    latest_lock = threading.Lock()
    latest: Optional[LatestFrame] = None
    sequence = 0
    last_error_at = 0.0

    def on_sample(sample: Any) -> None:
        nonlocal latest, sequence, last_error_at
        try:
            decoded = decode_json_payload(sample.payload)
            objects = collect_bbox_objects(decoded)
            if not objects:
                raise ValueError("payload does not contain any bbox objects")
            boxes = [parse_bbox(item, i) for i, item in enumerate(objects)]
            sequence += 1
            frame = LatestFrame(
                boxes=boxes,
                key=str(sample.key_expr),
                sequence=sequence,
                received_at=time.monotonic(),
            )
            with latest_lock:
                latest = frame
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            now = time.monotonic()
            if now - last_error_at >= 1.0:
                print(f"Ignored invalid bbox payload: {error}")
                last_error_at = now

    session = zenoh.open(build_config(args))
    subscriber = session.declare_subscriber(args.key, on_sample)
    print(
        f"Subscribed to {args.key}; displaying fixed XY rectangles in metres. "
        "Close the window or press Ctrl+C to stop."
    )

    figure, axes = plt.subplots(
        num="UeSim Zenoh BBox 2D Viewer",
        figsize=(args.image_width / args.dpi, args.image_height / args.dpi),
        dpi=args.dpi,
    )
    axes.set_xlabel("X / Forward (m)")
    axes.set_ylabel("Y / Left (m)")
    axes.set_xlim(args.x_min, args.x_max)
    axes.set_ylim(args.y_min, args.y_max)
    axes.set_aspect("equal", adjustable="box")
    axes.grid(True, linestyle="--", alpha=0.35)
    axes.set_title("UeSim BBoxes — fixed XY view")
    status_text = figure.text(0.02, 0.02, "Waiting for bbox data...", family="monospace")
    colors = ("tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown")
    artists: List[Tuple[Any, Any, Any, Any]] = []

    def add_artists(index: int) -> Tuple[Any, Any, Any, Any]:
        color = colors[index % len(colors)]
        polygon = Polygon(
            [(0.0, 0.0)],
            closed=True,
            facecolor=color,
            edgecolor=color,
            linewidth=2.0,
            alpha=0.25,
        )
        axes.add_patch(polygon)
        center, = axes.plot([], [], marker="o", color=color, markersize=6, linestyle="None")
        forward = FancyArrowPatch(
            (0.0, 0.0),
            (0.0, 0.0),
            arrowstyle="-|>",
            mutation_scale=14,
            color=color,
            linewidth=2.0,
        )
        axes.add_patch(forward)
        label = axes.text(0.0, 0.0, "", color=color, fontsize=9)
        return polygon, center, forward, label

    def update(_frame_index: int):
        with latest_lock:
            frame = latest
        if frame is None:
            return []

        while len(artists) < len(frame.boxes):
            artists.append(add_artists(len(artists)))

        rectangles = [oriented_rectangle(box) for box in frame.boxes]
        visible: List[Any] = []
        for index, artist_set in enumerate(artists):
            polygon, center_point, forward_arrow, label = artist_set
            is_visible = index < len(frame.boxes)
            for artist in artist_set:
                artist.set_visible(is_visible)
            if not is_visible:
                continue

            box = frame.boxes[index]
            polygon.set_xy(rectangles[index])
            center = (box.center[0], box.center[1])
            center_point.set_data([center[0]], [center[1]])

            direction = (box.forward[0], box.forward[1])
            direction_length = math.hypot(direction[0], direction[1])
            if direction_length > 1e-9:
                direction = (
                    direction[0] / direction_length,
                    direction[1] / direction_length,
                )
            arrow_length = max(
                abs(box.extent[0]) * 1.2,
                0.5,
            )
            arrow_end = (
                center[0] + direction[0] * arrow_length,
                center[1] + direction[1] * arrow_length,
            )
            forward_arrow.set_positions(center, arrow_end)
            label.set_position(center)
            label.set_text(f" {box.label}")
            visible.extend(artist_set)

        axes.set_title(f"UeSim BBoxes — fixed XY view — {len(frame.boxes)} objects")
        status_text.set_text(
            f"topic: {frame.key}   message: {frame.sequence}   "
            f"boxes: {len(frame.boxes)}   age: {time.monotonic() - frame.received_at:.2f}s"
        )
        visible.append(status_text)
        return visible

    animation = FuncAnimation(
        figure,
        update,
        interval=max(10, args.interval_ms),
        blit=False,
        cache_frame_data=False,
    )
    figure._bbox_animation = animation

    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        subscriber.undeclare()
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
