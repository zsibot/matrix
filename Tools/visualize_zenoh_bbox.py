#!/usr/bin/env python3
"""Visualize UeSim bounding boxes in a 2D XY top-down view over Zenoh.

The default topic and endpoint match the UeSim Zenoh setup:

    python3 Tools/visualize_zenoh_bbox.py

Dependencies:

    pip install eclipse-zenoh matplotlib

The viewer accepts the ROS-coordinate, metre-unit JSON emitted by the Blueprint
node ``Actor BBox To JSON String``. A direct bbox object, ``{"bbox": {...}}``,
a list of bbox objects, and ``{"bboxes": [...]}`` are all supported.
Categories may be provided in category/type/class fields or vehicle/human
groups. Vehicles are blue, humans orange, and unclassified boxes gray.
"""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
import textwrap
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import zenoh
except ImportError:
    zenoh = None

try:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    from matplotlib.lines import Line2D
    from matplotlib.patches import Polygon, FancyArrowPatch
    from matplotlib.widgets import Slider
except ImportError:
    plt = None
    FuncAnimation = None
    Polygon = None
    FancyArrowPatch = None


Vec3 = Tuple[float, float, float]
CATEGORY_COLORS = {"vehicle": "tab:blue", "human": "tab:orange", "unknown": "tab:gray"}

BOX_EDGES: Tuple[Tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
)


@dataclass
class BBox:
    center: Vec3
    extent: Vec3
    size: Vec3
    rotation: Vec3  # pitch, yaw, roll in degrees
    forward: Vec3
    corners: List[Vec3]
    label: str
    category: str = "unknown"
    velocity: Optional[Vec3] = None
    speed: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LatestFrame:
    boxes: List[BBox]
    key: str
    sequence: int
    received_at: float
    category_counts: Dict[str, int] = field(default_factory=dict)
    invalid_boxes: List[str] = field(default_factory=list)
    invalid_records: List[Dict[str, Any]] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Display UeSim vehicle and human bboxes in a 2D XY top-down view."
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
    return parser.parse_args()


def build_config(args: argparse.Namespace):
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
    text = payload_to_bytes(payload).decode("utf-8", errors="strict")
    text = text.strip("\x00 \t\r\n")
    value: Any = json.loads(text)

    # Also accept a JSON document that was itself encoded as a JSON string.
    if isinstance(value, str):
        value = json.loads(value)
    return value


def bbox_category(value: Dict[str, Any]) -> str:
    fields = {str(key).lower(): item for key, item in value.items()}
    for key in ("category", "type", "class"):
        category = str(fields.get(key, "")).strip().lower()
        if category:
            return category
    return "unknown"


def collect_bbox_objects(value: Any, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Flatten all groups, keeping category and actor identity across wrappers."""
    inherited = dict(metadata or {})
    if isinstance(value, str):
        try:
            return collect_bbox_objects(json.loads(value), inherited)
        except json.JSONDecodeError:
            return []

    if isinstance(value, list):
        result: List[Dict[str, Any]] = []
        for item in value:
            result.extend(collect_bbox_objects(item, inherited))
        return result
    if not isinstance(value, dict):
        return []

    category = bbox_category(value)
    if category != "unknown":
        inherited["category"] = category
    for key in ('velocity', 'speed', 'velocity_unit'):
        if key in value:
            inherited[key] = value[key]
    identity = {key: value[key] for key in ("label", "name", "id") if key in value}
    if identity:
        for key in ("label", "name", "id"):
            inherited.pop(key, None)
        inherited.update(identity)

    if isinstance(value.get("center"), dict) and isinstance(value.get("extent"), dict):
        return [{**value, **inherited}]

    if "bbox" in value:
        # Actor-level custom fields belong to the same record as its geometry.
        actor_metadata = {key: item for key, item in value.items() if key != "bbox"}
        actor_metadata.update(inherited)
        records = collect_bbox_objects(value["bbox"], actor_metadata)
        return records or [{**value, **inherited}]

    wrappers = {"bboxes", "bbox", "objects", "actors", "dynamicinfo", "data"}
    groups = {"vehicle": "vehicle", "vehicles": "vehicle", "human": "human", "humans": "human"}
    result = []
    for object_id, item in value.items():
        key = str(object_id).lower()
        if key in {"category", "type", "class", "label", "name", "id", "velocity", "speed", "velocity_unit"}:
            continue
        child_metadata = dict(inherited)
        if key in groups:
            child_metadata["category"] = groups[key]
        elif key not in wrappers and not any(field in child_metadata for field in ("label", "name", "id")):
            child_metadata["label"] = str(object_id)
        result.extend(collect_bbox_objects(item, child_metadata))
    if not result and category != "unknown":
        # UE may publish only Category when Get Actor BBox fails. Keep this
        # record for diagnostics; never invent a position for it.
        return [{**value, **inherited}]
    return result


def finite_number(value: Any, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} is not finite")
    return number


def parse_vec3(value: Any, field_name: str, scale: float) -> Vec3:
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


def parse_bbox(value: Dict[str, Any], index: int, scale: float) -> BBox:
    from bbox_motion import parse_motion
    velocity, speed = parse_motion(value)
    center = parse_vec3(value.get("center"), "center", scale)
    extent = parse_vec3(value.get("extent"), "extent", scale)

    if isinstance(value.get("size"), dict):
        size = parse_vec3(value["size"], "size", scale)
    else:
        size = tuple(component * 2.0 for component in extent)  # type: ignore[assignment]

    forward = parse_vec3(value.get("forward"), "forward", 1.0)
    forward_length = math.sqrt(sum(component * component for component in forward))
    if forward_length > 1e-9:
        forward = tuple(component / forward_length for component in forward)  # type: ignore[assignment]

    raw_corners = value.get("corners")
    if not isinstance(raw_corners, list) or len(raw_corners) != 8:
        raise ValueError("corners must contain exactly 8 x/y/z objects")
    corners = [parse_vec3(corner, f"corners[{i}]", scale) for i, corner in enumerate(raw_corners)]

    label_value = value.get("label", value.get("name", value.get("id", f"bbox {index}")))
    return BBox(
        center=center,
        extent=extent,
        size=size,
        rotation=parse_rotation(value.get("rotation")),
        forward=forward,
        corners=corners,
        label=str(label_value),
        category=bbox_category(value),
        velocity=velocity,
        speed=speed,
        raw=value,
    )


def edge_segments(box: BBox) -> List[Tuple[Vec3, Vec3]]:
    return [(box.corners[start], box.corners[end]) for start, end in BOX_EDGES]


def parse_frame(value: Any, key: str, sequence: int, scale: float = 1.0) -> LatestFrame:
    frame = LatestFrame([], key, sequence, time.monotonic())
    for index, item in enumerate(collect_bbox_objects(value)):
        category = bbox_category(item)
        frame.category_counts[category] = frame.category_counts.get(category, 0) + 1
        try:
            frame.boxes.append(parse_bbox(item, index, scale))
        except (TypeError, ValueError, OverflowError) as error:
            label = item.get("label", item.get("name", item.get("id", f"bbox {index}")))
            frame.invalid_boxes.append(f"[{category}] {label}: {error}")
            frame.invalid_records.append(item)
    return frame


def actor_details(frame: LatestFrame) -> str:
    """Full precision geometry and source fields, with no actor count limit."""
    sections = []
    for index, box in enumerate(frame.boxes, 1):
        details = {
            'label': box.label, 'category': box.category,
            'center (m)': box.center, 'extent (m)': box.extent,
            'size (m)': box.size, 'rotation (pitch, yaw, roll deg)': box.rotation,
            'forward (unit vector)': box.forward,
            'velocity (m/s)': box.velocity, 'speed (m/s)': box.speed,
            'corners (m)': box.corners,
            'source fields': box.raw,
        }
        sections.append(f'ACTOR {index}: {box.label}\n' + json.dumps(details, ensure_ascii=False, indent=2))
    for error, record in zip(frame.invalid_boxes, frame.invalid_records):
        sections.append(f'INVALID ACTOR: {error}\n' + json.dumps(record, ensure_ascii=False, indent=2))
    return '\n\n'.join(sections) or 'No actors in this frame.'


class ActorDetailsPanel:
    """Scrollable text inside Matplotlib; wheel and scrollbar preserve position."""
    def __init__(self, figure):
        self.figure = figure
        self.axes = figure.add_axes((0.53, 0.10, 0.42, 0.82))
        self.axes.set_axis_off()
        self.axes.set_title('All actor details · scroll to read', fontsize=11)
        self.text = self.axes.text(0, 1, '', va='top', family='monospace', fontsize=9,
                                   transform=self.axes.transAxes, clip_on=True)
        self.scroll_axes = figure.add_axes((0.965, 0.10, 0.015, 0.82))
        self.slider = Slider(self.scroll_axes, '', 0, 1, valinit=1, orientation='vertical')
        self.slider.valtext.set_visible(False)
        self.slider.on_changed(self._scroll)
        self.content = 'Waiting for bbox data...'
        self.lines = []
        self.offset = 0
        self.visible_lines = 1
        self.sequence = None
        self.geometry = None
        self.syncing = False
        figure.canvas.mpl_connect('scroll_event', self._wheel)
        figure.canvas.mpl_connect('resize_event', lambda event: self.refresh())
        self.refresh()

    def update(self, frame):
        geometry = (self.axes.bbox.width, self.axes.bbox.height, self.figure.dpi)
        if self.sequence != frame.sequence:
            self.content = actor_details(frame)
            self.sequence = frame.sequence
            self.refresh()
        elif geometry != self.geometry:
            self.refresh()

    def refresh(self):
        self.geometry = (self.axes.bbox.width, self.axes.bbox.height, self.figure.dpi)
        font_pixels = 9 * self.figure.dpi / 72
        columns = max(8, int(self.axes.bbox.width / (font_pixels * 0.65)))
        self.visible_lines = max(1, int(self.axes.bbox.height / (font_pixels * 1.4)))
        self.lines = [part for line in self.content.splitlines()
                      for part in (textwrap.wrap(line, width=columns, replace_whitespace=False,
                                                drop_whitespace=False) or [''])]
        self.render()

    def render(self):
        maximum = max(0, len(self.lines) - self.visible_lines)
        self.offset = max(0, min(self.offset, maximum))
        self.text.set_text('\n'.join(self.lines[self.offset:self.offset + self.visible_lines]))
        self.syncing = True
        try:
            self.slider.set_val(1 - self.offset / maximum if maximum else 1)
        finally:
            self.syncing = False

    def _scroll(self, value):
        if not self.syncing:
            self.offset = round((1 - value) * max(0, len(self.lines) - self.visible_lines))
            self.render()
            self.figure.canvas.draw_idle()

    def _wheel(self, event):
        if event.inaxes in (self.axes, self.scroll_axes):
            self.offset -= int(event.step * 4)
            self.render()
            self.figure.canvas.draw_idle()


def xy_footprint(box: BBox) -> List[Tuple[float, float]]:
    """Project all eight corners onto XY, including pitched/rolled boxes."""
    points = sorted(set((p[0], p[1]) for p in box.corners))
    if len(points) <= 2:
        return points

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def half_hull(ordered):
        hull = []
        for point in ordered:
            while len(hull) >= 2 and cross(hull[-2], hull[-1], point) <= 0:
                hull.pop()
            hull.append(point)
        return hull

    return half_hull(points)[:-1] + half_hull(reversed(points))[:-1]


def axis_limits(boxes: Sequence[BBox]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    points = [point for box in boxes for point in box.corners]
    points.extend(box.center for box in boxes)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]

    minimum_span = 1.0
    span = max(max(xs) - min(xs), max(ys) - min(ys), minimum_span)
    half_span = span * 0.65
    midpoint = (
        (min(xs) + max(xs)) * 0.5,
        (min(ys) + max(ys)) * 0.5,
    )
    lower = tuple(component - half_span for component in midpoint)
    upper = tuple(component + half_span for component in midpoint)
    return lower, upper  # type: ignore[return-value]


def main() -> int:
    args = parse_args()
    missing = []
    if zenoh is None:
        missing.append("eclipse-zenoh")
    if plt is None:
        missing.append("matplotlib")
    if missing:
        print("Missing dependencies. Install with:", file=__import__("sys").stderr)
        print(f"  pip install {' '.join(missing)}", file=__import__("sys").stderr)
        return 2

    # Blueprint output is already ROS X-forward/Y-left/Z-up in metres.
    scale = 1.0
    latest_lock = threading.Lock()
    latest: Optional[LatestFrame] = None
    sequence = 0
    last_error_at = 0.0

    def on_sample(sample: Any) -> None:
        nonlocal latest, sequence, last_error_at
        try:
            decoded = decode_json_payload(sample.payload)
            sequence += 1
            frame = parse_frame(decoded, str(sample.key_expr), sequence, scale)
            with latest_lock:
                latest = frame
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            now = time.monotonic()
            if now - last_error_at >= 1.0:
                print(f"Ignored invalid bbox payload: {error}")
                last_error_at = now

    session = zenoh.open(build_config(args))
    subscriber = session.declare_subscriber(args.key, on_sample)
    print(f"Subscribed to {args.key}; waiting for bbox JSON. Close the plot or press Ctrl+C to stop.")

    figure = plt.figure("UeSim Zenoh BBox 2D Viewer", figsize=(16, 9))
    axes = figure.add_axes((0.06, 0.18, 0.42, 0.74))
    details_panel = ActorDetailsPanel(figure)
    figure._actor_details_panel = details_panel
    axes.set_xlabel("X / Forward (m)")
    axes.set_ylabel("Y / Left (m)")
    axes.set_aspect("equal", adjustable="box")
    axes.grid(True, linestyle="--", alpha=0.3)
    axes.set_title("UeSim Bounding Boxes — 2D XY Top View")
    status_text = figure.text(0.02, 0.02, "Waiting for bbox data...", family="monospace")

    axes.legend(handles=[
        Line2D([0], [0], color=color, lw=2, label=category)
        for category, color in CATEGORY_COLORS.items()
    ] + [Line2D([0], [0], color='#24a88b', lw=2, label='velocity (1 s displacement)')], loc="upper right")
    artists: List[Tuple[Any, ...]] = []

    def add_artist(index: int) -> Tuple[Any, ...]:
        color = CATEGORY_COLORS["unknown"]
        outline = Polygon([(0, 0)], closed=True, facecolor=color, edgecolor=color,
                          linewidth=2.0, alpha=0.4)
        axes.add_patch(outline)
        center, = axes.plot([], [], marker="o", color=color, markersize=4, linestyle="None")
        forward = FancyArrowPatch((0, 0), (0, 0), arrowstyle="-|>",
                                  mutation_scale=12, color=color, linewidth=1.8)
        axes.add_patch(forward)
        label = axes.annotate("", (0, 0), xytext=(5, 5), textcoords="offset points", fontsize=8)
        velocity = FancyArrowPatch((0, 0), (0, 0), arrowstyle="-|>",
                                   mutation_scale=12, color='#24a88b', linewidth=2)
        axes.add_patch(velocity)
        return outline, center, forward, label, velocity

    def update(_frame_index: int):
        with latest_lock:
            frame = latest
        if frame is None:
            return []
        details_panel.update(frame)

        while len(artists) < len(frame.boxes):
            artists.append(add_artist(len(artists)))

        visible_artists: List[Any] = []
        status_lines = [
            f"topic: {frame.key}",
            f"message: {frame.sequence}   boxes: {len(frame.boxes)}   age: {time.monotonic() - frame.received_at:.2f}s",
            "   ".join(f"{category}: {sum(box.category == category for box in frame.boxes)}/{frame.category_counts.get(category, 0)} drawn"
                       for category in ("vehicle", "human")),
        ]

        for index, artist_set in enumerate(artists):
            outline, center_point, forward_arrow, label, velocity_arrow = artist_set
            is_visible = index < len(frame.boxes)
            for artist in artist_set:
                artist.set_visible(is_visible)
            if not is_visible:
                continue

            box = frame.boxes[index]
            color = CATEGORY_COLORS.get(box.category, CATEGORY_COLORS["unknown"])
            outline.set_facecolor(color)
            outline.set_edgecolor(color)
            forward_arrow.set_color(color)
            center_point.set_color(color)
            label.set_color(color)
            from bbox_motion import speed_label
            label.set_text(f"{box.category} | {box.label} | {speed_label(box.speed)}")
            label.xy = box.center[:2]
            outline.set_xy(xy_footprint(box))
            center_point.set_data([box.center[0]], [box.center[1]])

            arrow_length = max(max(box.extent[:2]) * 1.5, 0.1)
            arrow_end = tuple(
                box.center[axis] + box.forward[axis] * arrow_length for axis in range(2)
            )
            forward_arrow.set_positions(box.center[:2], arrow_end)
            velocity_arrow.set_visible(box.velocity is not None and math.hypot(*box.velocity[:2]) > .01)
            if box.velocity is not None:
                velocity_arrow.set_positions(box.center[:2], tuple(
                    box.center[i] + box.velocity[i] * scale for i in range(2)))
            visible_artists.extend(artist_set)
        if frame.invalid_boxes:
            status_lines.append(f"Missing/invalid geometry: {len(frame.invalid_boxes)} (not drawn)")
        if frame.boxes:
            lower, upper = axis_limits(frame.boxes)
            axes.set_xlim(lower[0], upper[0])
            axes.set_ylim(lower[1], upper[1])
        status_text.set_text("\n".join(status_lines))
        visible_artists.append(status_text)
        return visible_artists

    animation = FuncAnimation(
        figure,
        update,
        interval=max(10, args.interval_ms),
        blit=False,
        cache_frame_data=False,
    )
    # Keep a live reference for Matplotlib backends that only weakly retain it.
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
