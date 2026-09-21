#!/usr/bin/env python3
"""Receive and display UeSim camera and LiDAR sensors over Zenoh.

The viewer understands the formats published by ARobotCameraSensorActor:

* ROS 2 ``sensor_msgs/msg/CompressedImage`` (XCDR1) containing the custom PNG
  encoding ``depth_m = R + G / 255``.
* Raw ``MDEP`` float32 payloads (versions 1 and 2), whose samples are metres.
* Infrared/thermal (and ordinary color) JPEG/PNG compressed images.
* Semantic PNG images with R=G=B=class ID, displayed with a fixed class palette.
* ROS 2 ``sensor_msgs/msg/PointCloud2`` as a top-down 2D height map.

Move the mouse over a window to inspect its source pixel or LiDAR grid cell.
Press Q or Escape to exit.
"""

from __future__ import annotations

import argparse
import json
import math
import signal
import struct
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import zenoh
except ImportError:
    zenoh = None


@dataclass
class CompressedImage:
    sec: int
    nanosec: int
    frame_id: str
    fmt: str
    data: bytes


@dataclass
class DepthFrame:
    key: str
    depth_m: "np.ndarray"
    sec: Optional[int] = None
    nanosec: Optional[int] = None
    frame_id: str = ""
    source_format: str = ""
    max_range_m: Optional[float] = None
    horizontal_fov_deg: Optional[float] = None


@dataclass
class ImageFrame:
    key: str
    image_bgr: "np.ndarray"
    sec: Optional[int] = None
    nanosec: Optional[int] = None
    frame_id: str = ""
    source_format: str = ""
    image_kind: str = "Infrared"


# Class IDs match RobotSemanticLabels.h. Colors are BGR for OpenCV, display only.
SEMANTIC_CLASSES = {
    0: ("background", (0, 0, 0)),
    10: ("drive_plane", (80, 180, 60)),
    20: ("drive_stair", (0, 165, 255)),
    30: ("drive_other", (200, 130, 30)),
    40: ("human", (60, 60, 230)),
    50: ("vehicle", (220, 80, 180)),
    255: ("unclassified", (160, 160, 160)),
}


@dataclass
class SemanticFrame:
    key: str
    labels: "np.ndarray"
    sec: Optional[int] = None
    nanosec: Optional[int] = None
    frame_id: str = ""
    source_format: str = "UeSim semantic PNG (class IDs)"


@dataclass
class PointCloudFrame:
    key: str
    xyz_m: "np.ndarray"
    sec: int
    nanosec: int
    frame_id: str
    source_format: str = "ROS2 sensor_msgs/msg/PointCloud2"


@dataclass(frozen=True)
class PointField:
    offset: int
    datatype: int
    count: int


SensorFrame = Union[DepthFrame, ImageFrame, SemanticFrame, PointCloudFrame]


@dataclass
class TopicStats:
    frames: int = 0
    first_time: float = 0.0
    last_print_time: float = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Receive and display UeSim camera images, depth maps, and LiDAR "
            "PointCloud2 height maps."
        )
    )
    parser.add_argument(
        "--key",
        default="rt/**",
        help="Zenoh key expression (default: rt/**). Example: rt/front_depth/**",
    )
    parser.add_argument(
        "--mode",
        choices=("router", "client", "peer"),
        default="client",
        help="Zenoh session mode (default: client)",
    )
    parser.add_argument(
        "--connect",
        action="append",
        default=None,
        help="Endpoint to connect to; may be repeated (default for client: tcp/127.0.0.1:7447)",
    )
    parser.add_argument(
        "--listen",
        action="append",
        default=None,
        help="Endpoint to listen on; may be repeated",
    )
    parser.add_argument(
        "--stream-type",
        choices=("auto", "depth", "infrared", "semantic", "lidar"),
        default="auto",
        help=(
            "How to decode compressed images: auto detects by topic/frame name and payload; "
            "depth accepts only depth images; infrared treats JPEG/PNG as thermal images; "
            "semantic accepts lossless class-ID PNGs; lidar accepts only ROS2 PointCloud2 "
            "(default: auto)"
        ),
    )
    parser.add_argument(
        "--depth-min",
        type=float,
        default=0.05,
        help="Fixed colormap minimum in metres (default: 0.05)",
    )
    parser.add_argument(
        "--depth-max",
        type=float,
        default=30.0,
        help="Fixed colormap maximum in metres (default: 30)",
    )
    parser.add_argument(
        "--auto-range",
        action="store_true",
        help="Use the valid minimum and maximum of each frame for the colormap",
    )
    parser.add_argument(
        "--colormap",
        choices=("turbo", "jet", "inferno", "magma", "plasma", "viridis", "gray"),
        default="turbo",
        help="Depth colormap (default: turbo)",
    )
    parser.add_argument(
        "--window-prefix",
        default="UeSim Sensor",
        help="Prefix used for OpenCV window names",
    )
    parser.add_argument(
        "--print-interval",
        type=float,
        default=1.0,
        help="Seconds between terminal status lines per topic (default: 1)",
    )
    parser.add_argument(
        "--lidar-range",
        type=float,
        default=40.0,
        help="LiDAR height-map half-width in metres (default: 40)",
    )
    parser.add_argument(
        "--lidar-resolution",
        type=float,
        default=0.1,
        help="LiDAR height-map metres per pixel (default: 0.1)",
    )
    parser.add_argument(
        "--height-min",
        type=float,
        default=-2.0,
        help="LiDAR colormap minimum Z in metres (default: -2)",
    )
    parser.add_argument(
        "--height-max",
        type=float,
        default=5.0,
        help="LiDAR colormap maximum Z in metres (default: 5)",
    )
    parser.add_argument(
        "--height-auto-range",
        action="store_true",
        help="Use each cloud's visible Z range for the LiDAR colormap",
    )
    return parser.parse_args()


def require_dependencies() -> None:
    missing = []
    if zenoh is None:
        missing.append("eclipse-zenoh")
    if np is None:
        missing.append("numpy")
    if cv2 is None:
        missing.append("opencv-python")
    if missing:
        raise RuntimeError(
            "Missing Python dependencies: "
            + ", ".join(missing)
            + ". Install with: pip install "
            + " ".join(missing)
        )


def build_zenoh_config(args: argparse.Namespace) -> "zenoh.Config":
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


def payload_bytes(payload) -> bytes:
    try:
        return bytes(payload)
    except TypeError:
        return payload.to_bytes()


def align4(offset: int) -> int:
    return (offset + 3) & ~3


def read_u32(data: bytes, offset: int) -> Tuple[int, int]:
    offset = align4(offset)
    if offset + 4 > len(data):
        raise ValueError("CDR uint32 is out of range")
    return struct.unpack_from("<I", data, offset)[0], offset + 4


def read_i32(data: bytes, offset: int) -> Tuple[int, int]:
    offset = align4(offset)
    if offset + 4 > len(data):
        raise ValueError("CDR int32 is out of range")
    return struct.unpack_from("<i", data, offset)[0], offset + 4


def read_u8(data: bytes, offset: int) -> Tuple[int, int]:
    if offset + 1 > len(data):
        raise ValueError("CDR uint8 is out of range")
    return data[offset], offset + 1


def read_cdr_string(data: bytes, offset: int) -> Tuple[str, int]:
    length, offset = read_u32(data, offset)
    if length == 0:
        return "", align4(offset)
    if offset + length > len(data):
        raise ValueError("CDR string is out of range")
    value = data[offset : offset + length]
    if value.endswith(b"\x00"):
        value = value[:-1]
    return value.decode("utf-8", errors="replace"), align4(offset + length)


def parse_compressed_image_cdr(data: bytes) -> Optional[CompressedImage]:
    # UeSim publishes XCDR1 little-endian with this four-byte encapsulation.
    if len(data) < 4 or data[:4] != b"\x00\x01\x00\x00":
        return None
    try:
        offset = 4
        sec, offset = read_i32(data, offset)
        nanosec, offset = read_u32(data, offset)
        frame_id, offset = read_cdr_string(data, offset)
        fmt, offset = read_cdr_string(data, offset)
        payload_size, offset = read_u32(data, offset)
        if payload_size <= 0 or offset + payload_size > len(data):
            return None
        return CompressedImage(
            sec=sec,
            nanosec=nanosec,
            frame_id=frame_id,
            fmt=fmt,
            data=data[offset : offset + payload_size],
        )
    except (ValueError, struct.error):
        return None


def parse_pointcloud2_cdr(data: bytes, key: str) -> Optional[PointCloudFrame]:
    """Decode the XYZ fields of a ROS2 PointCloud2 XCDR1 payload."""
    if len(data) < 4 or data[:4] not in (b"\x00\x01\x00\x00", b"\x00\x00\x00\x00"):
        return None
    little_endian_cdr = data[:2] == b"\x00\x01"
    if not little_endian_cdr:
        # UeSim publishes little-endian XCDR1. Rejecting other encapsulations is
        # safer than interpreting their Header/dimensions with the helpers above.
        return None

    try:
        offset = 4
        sec, offset = read_i32(data, offset)
        nanosec, offset = read_u32(data, offset)
        if nanosec >= 1_000_000_000:
            return None
        frame_id, offset = read_cdr_string(data, offset)
        height, offset = read_u32(data, offset)
        width, offset = read_u32(data, offset)
        field_count, offset = read_u32(data, offset)
        if height <= 0 or width <= 0 or height * width > 100_000_000:
            return None
        if not 1 <= field_count <= 128:
            return None

        fields: Dict[str, PointField] = {}
        for _ in range(field_count):
            name, offset = read_cdr_string(data, offset)
            field_offset, offset = read_u32(data, offset)
            datatype, offset = read_u8(data, offset)
            count, offset = read_u32(data, offset)
            fields[name] = PointField(field_offset, datatype, count)

        is_bigendian, offset = read_u8(data, offset)
        point_step, offset = read_u32(data, offset)
        row_step, offset = read_u32(data, offset)
        payload_size, offset = read_u32(data, offset)
        if point_step <= 0 or row_step < width * point_step:
            return None
        if payload_size < row_step * height or offset + payload_size > len(data):
            return None
        if not all(name in fields for name in ("x", "y", "z")):
            return None

        raw = memoryview(data)[offset : offset + payload_size]
        endian = ">" if is_bigendian else "<"
        columns = []
        for name in ("x", "y", "z"):
            field = fields[name]
            if field.count < 1 or field.datatype not in (7, 8):
                return None
            item_size = 4 if field.datatype == 7 else 8
            if field.offset + item_size > point_step:
                return None
            dtype = np.dtype(endian + ("f4" if item_size == 4 else "f8"))
            values = np.ndarray(
                shape=(height, width),
                dtype=dtype,
                buffer=raw,
                offset=field.offset,
                strides=(row_step, point_step),
            )
            columns.append(values.reshape(-1))

        xyz_m = np.column_stack(columns).astype(np.float32, copy=True)
        return PointCloudFrame(
            key=key,
            xyz_m=xyz_m,
            sec=sec,
            nanosec=nanosec,
            frame_id=frame_id,
        )
    except (BufferError, TypeError, ValueError, struct.error):
        return None


def decode_uesim_depth_png(encoded: bytes) -> Optional["np.ndarray"]:
    image_bytes = np.frombuffer(encoded, dtype=np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_UNCHANGED)
    if image is None or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] < 3:
        return None

    # OpenCV returns BGR(A). UeSim's encoded R and G therefore live in channel
    # indices 2 and 1. Channel 0 is expected to be zero.
    integer_m = image[:, :, 2]
    fractional_255_m = image[:, :, 1]
    blue = image[:, :, 0]

    # Reject ordinary PNG images when subscribing to a broad key such as rt/**.
    blue_zero_ratio = float(np.count_nonzero(blue == 0)) / float(blue.size)
    if blue_zero_ratio < 0.99:
        return None

    depth_m = integer_m.astype(np.float32)
    depth_m += fractional_255_m.astype(np.float32) / 255.0
    invalid = (integer_m == 0) & (fractional_255_m == 0)
    depth_m[invalid] = np.nan
    return depth_m


def decode_compressed_color_image(encoded: bytes) -> Optional["np.ndarray"]:
    image_bytes = np.frombuffer(encoded, dtype=np.uint8)
    # Force a three-channel BGR image so grayscale and alpha-bearing thermal
    # palettes follow the same display and mouse-inspection path.
    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
    if image is None or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        return None
    return image


def semantic_frame_from_message(key: str, message: CompressedImage) -> Optional[SemanticFrame]:
    # Do not let a JPEG relabelled as PNG silently corrupt class IDs.
    if "png" not in message.fmt.lower() or not message.data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    image = cv2.imdecode(np.frombuffer(message.data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.dtype != np.uint8:
        return None
    if image.ndim == 2:
        labels = image.copy()
    elif image.ndim == 3 and image.shape[2] in (3, 4):
        if not np.array_equal(image[:, :, 0], image[:, :, 1]) or not np.array_equal(image[:, :, 0], image[:, :, 2]):
            return None
        if image.shape[2] == 4 and not np.all(image[:, :, 3] == 255):
            return None
        labels = image[:, :, 0].copy()
    else:
        return None
    return SemanticFrame(key, labels, message.sec, message.nanosec, message.frame_id)


def has_semantic_hint(key: str, frame_id: str) -> bool:
    text = f"{key}/{frame_id}".lower()
    return "semantic" in text or "segmentation" in text


def has_depth_hint(key: str, frame_id: str) -> bool:
    text = f"{key}/{frame_id}".lower()
    return "depth" in text or "mdep" in text


def has_infrared_hint(key: str, frame_id: str) -> bool:
    text = f"/{key}/{frame_id}/".lower()
    return (
        "infrared" in text
        or "thermal" in text
        or "ir_camera" in text
        or "/ir/" in text
        or "/ir_" in text
        or "_ir/" in text
    )


def parse_mdep(data: bytes, key: str) -> Optional[DepthFrame]:
    if len(data) < 24 or data[:4] != b"MDEP":
        return None
    try:
        version, width, height = struct.unpack_from("<iii", data, 4)
        max_range_m, horizontal_fov_deg = struct.unpack_from("<ff", data, 16)
        if version not in (1, 2) or width <= 0 or height <= 0:
            return None
        if width * height > 100_000_000:
            return None

        if version == 1:
            depth_offset = 24
            sec = None
            nanosec = None
        else:
            if len(data) < 32:
                return None
            sec, nanosec = struct.unpack_from("<iI", data, 24)
            depth_offset = 32

        count = width * height
        if depth_offset + count * 4 > len(data):
            return None
        depth_m = np.frombuffer(data, dtype="<f4", count=count, offset=depth_offset)
        depth_m = depth_m.reshape((height, width)).copy()
        depth_m[~np.isfinite(depth_m) | (depth_m <= 0.0)] = np.nan
        return DepthFrame(
            key=key,
            depth_m=depth_m,
            sec=sec,
            nanosec=nanosec,
            source_format=f"MDEP v{version} float32",
            max_range_m=float(max_range_m),
            horizontal_fov_deg=float(horizontal_fov_deg),
        )
    except (ValueError, struct.error):
        return None


def decode_depth_sample(key: str, data: bytes) -> Optional[DepthFrame]:
    raw_frame = parse_mdep(data, key)
    if raw_frame is not None:
        return raw_frame

    message = parse_compressed_image_cdr(data)
    if message is None or message.fmt.lower() != "png":
        return None
    depth_m = decode_uesim_depth_png(message.data)
    if depth_m is None:
        return None
    return DepthFrame(
        key=key,
        depth_m=depth_m,
        sec=message.sec,
        nanosec=message.nanosec,
        frame_id=message.frame_id,
        source_format="UeSim PNG (R + G/255 metres)",
    )


def image_frame_from_message(
    key: str,
    message: CompressedImage,
    image_kind: str = "Infrared",
) -> Optional[ImageFrame]:
    image = decode_compressed_color_image(message.data)
    if image is None:
        return None
    return ImageFrame(
        key=key,
        image_bgr=image,
        sec=message.sec,
        nanosec=message.nanosec,
        frame_id=message.frame_id,
        source_format=f"{message.fmt.upper()} compressed image",
        image_kind=image_kind,
    )


def decode_sensor_sample(
    key: str,
    data: bytes,
    stream_type: str,
) -> Optional[SensorFrame]:
    if stream_type in ("auto", "lidar"):
        cloud = parse_pointcloud2_cdr(data, key)
        if cloud is not None:
            return cloud
        if stream_type == "lidar":
            return None

    if stream_type in ("auto", "depth"):
        raw_frame = parse_mdep(data, key)
        if raw_frame is not None:
            return raw_frame

    message = parse_compressed_image_cdr(data)
    if message is None:
        return None

    if stream_type == "semantic":
        return semantic_frame_from_message(key, message)

    if stream_type == "auto" and has_semantic_hint(key, message.frame_id):
        # An all-background semantic PNG would otherwise look like an empty depth map.
        # On invalid semantic data, reject rather than fall through to another decoder.
        return semantic_frame_from_message(key, message)

    if stream_type == "infrared":
        return image_frame_from_message(key, message, "Infrared")

    if stream_type == "depth":
        if message.fmt.lower() != "png":
            return None
        depth_m = decode_uesim_depth_png(message.data)
        if depth_m is None:
            return None
        return DepthFrame(
            key=key,
            depth_m=depth_m,
            sec=message.sec,
            nanosec=message.nanosec,
            frame_id=message.frame_id,
            source_format="UeSim PNG (R + G/255 metres)",
        )

    # Auto mode prioritizes explicit topic/frame hints. This is important for
    # dark or single-channel thermal palettes, which can otherwise resemble the
    # custom depth PNG because most of their blue pixels may be zero.
    if has_infrared_hint(key, message.frame_id):
        return image_frame_from_message(key, message, "Infrared")

    if has_depth_hint(key, message.frame_id):
        if message.fmt.lower() != "png":
            return None
        depth_m = decode_uesim_depth_png(message.data)
        if depth_m is None:
            return None
        return DepthFrame(
            key=key,
            depth_m=depth_m,
            sec=message.sec,
            nanosec=message.nanosec,
            frame_id=message.frame_id,
            source_format="UeSim PNG (R + G/255 metres)",
        )

    if message.fmt.lower() == "png":
        depth_m = decode_uesim_depth_png(message.data)
        if depth_m is not None:
            return DepthFrame(
                key=key,
                depth_m=depth_m,
                sec=message.sec,
                nanosec=message.nanosec,
                frame_id=message.frame_id,
                source_format="UeSim PNG (R + G/255 metres)",
            )

    image_kind = "Infrared" if has_infrared_hint(key, message.frame_id) else "Color"
    return image_frame_from_message(key, message, image_kind)


def colormap_code(name: str) -> Optional[int]:
    if name == "gray":
        return None
    names = {
        "turbo": "COLORMAP_TURBO",
        "jet": "COLORMAP_JET",
        "inferno": "COLORMAP_INFERNO",
        "magma": "COLORMAP_MAGMA",
        "plasma": "COLORMAP_PLASMA",
        "viridis": "COLORMAP_VIRIDIS",
    }
    attribute = names[name]
    # Older OpenCV versions may not have every map. JET is always available.
    return getattr(cv2, attribute, cv2.COLORMAP_JET)


def valid_depth_values(depth_m: "np.ndarray") -> "np.ndarray":
    valid = np.isfinite(depth_m) & (depth_m > 0.0)
    return depth_m[valid]


def colorize_depth(
    depth_m: "np.ndarray",
    minimum_m: float,
    maximum_m: float,
    auto_range: bool,
    map_name: str,
) -> Tuple["np.ndarray", float, float]:
    valid = np.isfinite(depth_m) & (depth_m > 0.0)
    values = depth_m[valid]

    display_min = float(minimum_m)
    display_max = float(maximum_m)
    if auto_range and values.size:
        display_min = float(np.min(values))
        display_max = float(np.max(values))
    if not math.isfinite(display_min):
        display_min = 0.0
    if not math.isfinite(display_max) or display_max <= display_min:
        display_max = display_min + 1.0

    normalized = np.zeros(depth_m.shape, dtype=np.uint8)
    if values.size:
        scale = 255.0 / (display_max - display_min)
        normalized[valid] = np.clip(
            (depth_m[valid] - display_min) * scale, 0.0, 255.0
        ).astype(np.uint8)

    code = colormap_code(map_name)
    if code is None:
        image = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
    else:
        image = cv2.applyColorMap(normalized, code)
    image[~valid] = (0, 0, 0)
    return image, display_min, display_max


def safe_window_key(key: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "_-/." else "_" for ch in key)


def timestamp_text(frame: SensorFrame) -> str:
    if frame.sec is None or frame.nanosec is None:
        return "timestamp unavailable"
    return f"{frame.sec}.{frame.nanosec:09d}"


def make_depth_display_image(
    frame: DepthFrame,
    mouse_xy: Optional[Tuple[int, int]],
    args: argparse.Namespace,
) -> "np.ndarray":
    image, display_min, display_max = colorize_depth(
        frame.depth_m,
        args.depth_min,
        args.depth_max,
        args.auto_range,
        args.colormap,
    )
    height, width = frame.depth_m.shape

    line1 = "Move mouse over image to inspect depth"
    if mouse_xy is not None:
        x, y = mouse_xy
        if 0 <= x < width and 0 <= y < height:
            distance_m = float(frame.depth_m[y, x])
            if math.isfinite(distance_m) and distance_m > 0.0:
                line1 = (
                    f"pixel=({x}, {y})  distance={distance_m:.4f} m  "
                    f"({distance_m * 100.0:.2f} cm)"
                )
                cv2.drawMarker(
                    image,
                    (x, y),
                    (255, 255, 255),
                    markerType=cv2.MARKER_CROSS,
                    markerSize=15,
                    thickness=1,
                )
            else:
                line1 = f"pixel=({x}, {y})  distance=INVALID / no hit"

    values = valid_depth_values(frame.depth_m)
    if values.size:
        measured_range = f"valid range={float(np.min(values)):.3f}..{float(np.max(values)):.3f} m"
    else:
        measured_range = "valid range=none"
    line2 = (
        f"{width}x{height}  {measured_range}  "
        f"display={display_min:.2f}..{display_max:.2f} m"
    )
    line3 = f"{frame.source_format}  stamp={timestamp_text(frame)}  Q/Esc: quit"

    panel_height = 76
    panel = np.full((panel_height, width, 3), 24, dtype=np.uint8)
    cv2.putText(panel, line1, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(panel, line2, (8, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (210, 210, 210), 1, cv2.LINE_AA)
    cv2.putText(panel, line3, (8, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (170, 170, 170), 1, cv2.LINE_AA)
    return np.vstack((image, panel))


def make_camera_display_image(
    frame: ImageFrame,
    mouse_xy: Optional[Tuple[int, int]],
) -> "np.ndarray":
    image = frame.image_bgr.copy()
    height, width = image.shape[:2]

    line1 = f"{frame.image_kind} image"
    if mouse_xy is not None:
        x, y = mouse_xy
        if 0 <= x < width and 0 <= y < height:
            blue, green, red = (int(value) for value in image[y, x])
            line1 = f"pixel=({x}, {y})  RGB=({red}, {green}, {blue})"
            cv2.drawMarker(
                image,
                (x, y),
                (255, 255, 255),
                markerType=cv2.MARKER_CROSS,
                markerSize=15,
                thickness=1,
            )

    frame_text = f"  frame={frame.frame_id}" if frame.frame_id else ""
    line2 = (
        f"{width}x{height}  {frame.source_format}{frame_text}  "
        f"stamp={timestamp_text(frame)}  Q/Esc: quit"
    )

    panel_height = 54
    panel = np.full((panel_height, width, 3), 24, dtype=np.uint8)
    cv2.putText(panel, line1, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(panel, line2, (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (190, 190, 190), 1, cv2.LINE_AA)
    return np.vstack((image, panel))


def semantic_class_name(label: int) -> str:
    return SEMANTIC_CLASSES[label][0] if label in SEMANTIC_CLASSES else "undefined"


def colorize_semantic(labels: "np.ndarray") -> "np.ndarray":
    # Undefined IDs remain inspectable and stand out in magenta; never remap the data.
    palette = np.full((256, 3), (255, 0, 255), dtype=np.uint8)
    for label, (_name, color) in SEMANTIC_CLASSES.items():
        palette[label] = color
    return palette[labels]


def make_semantic_display_image(
    frame: SemanticFrame,
    mouse_xy: Optional[Tuple[int, int]],
) -> "np.ndarray":
    image = colorize_semantic(frame.labels)
    height, width = frame.labels.shape
    line1 = "Semantic classes: move mouse over image to inspect ID"
    if mouse_xy is not None:
        x, y = mouse_xy
        if 0 <= x < width and 0 <= y < height:
            label = int(frame.labels[y, x])
            line1 = f"pixel=({x}, {y})  class_id={label}  {semantic_class_name(label)}"
            cv2.drawMarker(image, (x, y), (255, 255, 255), cv2.MARKER_CROSS, 15, 1)

    # Pad small images instead of resampling class boundaries or altering mouse coordinates.
    canvas_width = max(width, 640)
    legend_rows = (len(SEMANTIC_CLASSES) + 1) // 2
    display = np.full((height + 82 + legend_rows * 22, canvas_width, 3), 24, dtype=np.uint8)
    display[:height, :width] = image
    panel = display[height:]
    cv2.putText(panel, line1, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
    line2 = f"{width}x{height}  frame={frame.frame_id or '-'}  stamp={timestamp_text(frame)}"
    cv2.putText(panel, line2, (8, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (210, 210, 210), 1, cv2.LINE_AA)
    cv2.putText(panel, "Class-ID PNG | magenta: undefined ID | Q/Esc: quit", (8, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (190, 190, 190), 1, cv2.LINE_AA)
    for index, (label, (name, color)) in enumerate(SEMANTIC_CLASSES.items()):
        x = 8 + (index % 2) * (canvas_width // 2)
        y = 78 + (index // 2) * 22
        cv2.rectangle(panel, (x, y), (x + 14, y + 14), color, -1)
        cv2.rectangle(panel, (x, y), (x + 14, y + 14), (210, 210, 210), 1)
        cv2.putText(panel, f"{label}: {name}", (x + 22, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (230, 230, 230), 1, cv2.LINE_AA)
    return display


def pointcloud_height_grid(
    xyz_m: "np.ndarray",
    half_range_m: float,
    resolution_m: float,
) -> Tuple["np.ndarray", int]:
    """Rasterize one cloud using the maximum LiDAR-frame Z per XY cell."""
    grid_size = int(math.ceil(2.0 * half_range_m / resolution_m))
    height_grid = np.full((grid_size, grid_size), -np.inf, dtype=np.float32)
    if xyz_m.size == 0:
        height_grid[:] = np.nan
        return height_grid, 0

    xyz = np.asarray(xyz_m, dtype=np.float32)
    valid = np.all(np.isfinite(xyz), axis=1)
    valid &= np.abs(xyz[:, 0]) < half_range_m
    valid &= np.abs(xyz[:, 1]) < half_range_m
    xyz = xyz[valid]
    if xyz.size == 0:
        height_grid[:] = np.nan
        return height_grid, 0

    # Image top is LiDAR +X (forward); image left is +Y (left).
    rows = np.floor((half_range_m - xyz[:, 0]) / resolution_m).astype(np.int64)
    cols = np.floor((half_range_m - xyz[:, 1]) / resolution_m).astype(np.int64)
    inside = (
        (rows >= 0)
        & (rows < grid_size)
        & (cols >= 0)
        & (cols < grid_size)
    )
    rows, cols, heights = rows[inside], cols[inside], xyz[inside, 2]
    np.maximum.at(height_grid, (rows, cols), heights)
    height_grid[~np.isfinite(height_grid)] = np.nan
    return height_grid, int(heights.size)


def make_lidar_display_image(
    frame: PointCloudFrame,
    mouse_xy: Optional[Tuple[int, int]],
    args: argparse.Namespace,
) -> "np.ndarray":
    height_grid, visible_points = pointcloud_height_grid(
        frame.xyz_m,
        args.lidar_range,
        args.lidar_resolution,
    )
    valid = np.isfinite(height_grid)
    heights = height_grid[valid]
    display_min = float(args.height_min)
    display_max = float(args.height_max)
    if args.height_auto_range and heights.size:
        display_min = float(np.percentile(heights, 1.0))
        display_max = float(np.percentile(heights, 99.0))
    if not math.isfinite(display_min):
        display_min = -2.0
    if not math.isfinite(display_max) or display_max <= display_min:
        display_max = display_min + 1.0

    normalized = np.zeros(height_grid.shape, dtype=np.uint8)
    if heights.size:
        normalized[valid] = np.clip(
            (height_grid[valid] - display_min)
            * (255.0 / (display_max - display_min)),
            0.0,
            255.0,
        ).astype(np.uint8)
    code = colormap_code(args.colormap)
    image = (
        cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
        if code is None
        else cv2.applyColorMap(normalized, code)
    )
    image[~valid] = (12, 12, 12)

    size = height_grid.shape[0]
    center = int(round(args.lidar_range / args.lidar_resolution))
    center = min(max(center, 0), size - 1)
    grid_step_m = 5.0
    grid_step_px = max(1, int(round(grid_step_m / args.lidar_resolution)))
    for radius_px in range(grid_step_px, center + 1, grid_step_px):
        cv2.circle(image, (center, center), radius_px, (80, 80, 80), 1, cv2.LINE_AA)
    cv2.line(image, (center, 0), (center, size - 1), (100, 100, 100), 1)
    cv2.line(image, (0, center), (size - 1, center), (100, 100, 100), 1)
    cv2.drawMarker(
        image,
        (center, center),
        (255, 255, 255),
        markerType=cv2.MARKER_CROSS,
        markerSize=13,
        thickness=1,
    )
    cv2.putText(image, "+X forward", (center + 8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)
    cv2.putText(image, "+Y left", (8, center - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)

    line1 = "Move mouse over map to inspect LiDAR height"
    if mouse_xy is not None:
        pixel_x, pixel_y = mouse_xy
        if 0 <= pixel_x < size and 0 <= pixel_y < size:
            forward_m = args.lidar_range - (pixel_y + 0.5) * args.lidar_resolution
            left_m = args.lidar_range - (pixel_x + 0.5) * args.lidar_resolution
            height_m = float(height_grid[pixel_y, pixel_x])
            if math.isfinite(height_m):
                line1 = (
                    f"XY=({forward_m:+.2f}, {left_m:+.2f}) m  "
                    f"height Z={height_m:+.3f} m"
                )
                cv2.drawMarker(image, (pixel_x, pixel_y), (255, 255, 255), cv2.MARKER_CROSS, 15, 1)
            else:
                line1 = f"XY=({forward_m:+.2f}, {left_m:+.2f}) m  no return"

    finite_source = np.all(np.isfinite(frame.xyz_m), axis=1)
    source_valid = int(np.count_nonzero(finite_source))
    occupied_cells = int(np.count_nonzero(valid))
    line2 = (
        f"points={source_valid}/{len(frame.xyz_m)}  in_map={visible_points}  "
        f"cells={occupied_cells}  area=+/-{args.lidar_range:g} m  "
        f"resolution={args.lidar_resolution:g} m/px"
    )
    line3 = (
        f"height colors={display_min:+.2f}..{display_max:+.2f} m  "
        f"frame={frame.frame_id or '-'}  stamp={timestamp_text(frame)}  Q/Esc: quit"
    )
    panel = np.full((76, size, 3), 24, dtype=np.uint8)
    cv2.putText(panel, line1, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(panel, line2, (8, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (205, 205, 205), 1, cv2.LINE_AA)
    cv2.putText(panel, line3, (8, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (170, 170, 170), 1, cv2.LINE_AA)
    return np.vstack((image, panel))


def make_display_image(
    frame: SensorFrame,
    mouse_xy: Optional[Tuple[int, int]],
    args: argparse.Namespace,
) -> "np.ndarray":
    if isinstance(frame, SemanticFrame):
        return make_semantic_display_image(frame, mouse_xy)
    if isinstance(frame, DepthFrame):
        return make_depth_display_image(frame, mouse_xy, args)
    if isinstance(frame, PointCloudFrame):
        return make_lidar_display_image(frame, mouse_xy, args)
    return make_camera_display_image(frame, mouse_xy)


def print_frame_status(frame: SensorFrame, stats: TopicStats, interval: float) -> None:
    now = time.monotonic()
    first_frame = stats.first_time == 0.0
    if first_frame:
        stats.first_time = now
    stats.frames += 1
    if not first_frame and now - stats.last_print_time < max(0.1, interval):
        return
    stats.last_print_time = now

    elapsed = now - stats.first_time
    fps_text = f"{stats.frames / elapsed:.1f}" if elapsed >= 0.25 else "warming-up"
    if isinstance(frame, PointCloudFrame):
        finite = np.all(np.isfinite(frame.xyz_m), axis=1)
        finite_xyz = frame.xyz_m[finite]
        if finite_xyz.size:
            ranges = np.linalg.norm(finite_xyz, axis=1)
            range_text = f"{float(np.min(ranges)):.3f}..{float(np.max(ranges)):.3f} m"
            height_text = f"{float(np.min(finite_xyz[:, 2])):+.3f}..{float(np.max(finite_xyz[:, 2])):+.3f} m"
        else:
            range_text = "none"
            height_text = "none"
        print(
            f"[LIDAR] key={frame.key} points={int(np.count_nonzero(finite))}/{len(frame.xyz_m)} "
            f"range={range_text} height={height_text} fps={fps_text} "
            f"frame={frame.frame_id or '-'}"
        )
        return
    if isinstance(frame, SemanticFrame):
        height, width = frame.labels.shape
        labels, counts = np.unique(frame.labels, return_counts=True)
        classes = ", ".join(
            f"{int(label)}:{semantic_class_name(int(label))}={int(count)}"
            for label, count in zip(labels, counts)
        )
        print(
            f"[SEMANTIC] key={frame.key} size={width}x{height} fps={fps_text} "
            f"frame={frame.frame_id or '-'} classes=[{classes}]"
        )
        return
    if isinstance(frame, ImageFrame):
        height, width = frame.image_bgr.shape[:2]
        print(
            f"[{frame.image_kind.upper()}] key={frame.key} size={width}x{height} "
            f"fps={fps_text} format={frame.source_format} frame={frame.frame_id or '-'}"
        )
        return

    values = valid_depth_values(frame.depth_m)
    total = int(frame.depth_m.size)
    valid_count = int(values.size)
    if valid_count:
        range_text = f"{float(np.min(values)):.3f}..{float(np.max(values)):.3f} m"
    else:
        range_text = "none"
    print(
        f"[DEPTH] key={frame.key} size={frame.depth_m.shape[1]}x{frame.depth_m.shape[0]} "
        f"valid={valid_count}/{total} range={range_text} fps={fps_text} "
        f"format={frame.source_format}"
    )


def main() -> int:
    args = parse_args()
    try:
        require_dependencies()
    except RuntimeError as error:
        print(f"[ERROR] {error}")
        return 2
    if args.depth_max <= args.depth_min:
        print("[ERROR] --depth-max must be greater than --depth-min")
        return 2
    if args.height_max <= args.height_min:
        print("[ERROR] --height-max must be greater than --height-min")
        return 2
    if args.lidar_range <= 0.0 or args.lidar_resolution <= 0.0:
        print("[ERROR] --lidar-range and --lidar-resolution must be positive")
        return 2
    lidar_grid_size = math.ceil(2.0 * args.lidar_range / args.lidar_resolution)
    if lidar_grid_size < 16 or lidar_grid_size > 4096:
        print("[ERROR] LiDAR map size must be between 16 and 4096 pixels")
        return 2

    stop_event = threading.Event()
    pending_lock = threading.Lock()
    pending_samples: Dict[str, bytes] = {}
    frames: Dict[str, SensorFrame] = {}
    mouse_positions: Dict[str, Tuple[int, int]] = {}
    stats_by_key: Dict[str, TopicStats] = {}
    windows_by_key: Dict[str, str] = {}

    def request_stop(_signum=None, _frame=None) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    config = build_zenoh_config(args)
    session = zenoh.open(config)

    def on_sample(sample) -> None:
        # Keep only the newest sample per topic. Decoding and all GUI operations
        # happen on the main thread, not on a Zenoh worker thread.
        key = str(sample.key_expr)
        data = payload_bytes(sample.payload)
        with pending_lock:
            pending_samples[key] = data

    subscriber = session.declare_subscriber(args.key, on_sample)
    print(
        f"[INFO] Listening for UeSim sensors: key={args.key}, "
        f"mode={args.mode}, stream_type={args.stream_type}"
    )
    print("[INFO] Move the mouse over a window to inspect its pixel; press Q or Escape to exit")

    try:
        while not stop_event.is_set():
            with pending_lock:
                samples = pending_samples.copy()
                pending_samples.clear()

            for key, data in samples.items():
                frame = decode_sensor_sample(key, data, args.stream_type)
                if frame is None:
                    continue
                frames[key] = frame
                stats = stats_by_key.setdefault(key, TopicStats())
                print_frame_status(frame, stats, args.print_interval)

                if key not in windows_by_key:
                    window = f"{args.window_prefix}: {safe_window_key(key)}"
                    windows_by_key[key] = window
                    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)

                    def on_mouse(event, x, y, _flags, topic) -> None:
                        if event == cv2.EVENT_MOUSEMOVE:
                            mouse_positions[topic] = (x, y)

                    cv2.setMouseCallback(window, on_mouse, key)

            for key, frame in frames.items():
                window = windows_by_key[key]
                display = make_display_image(frame, mouse_positions.get(key), args)
                cv2.imshow(window, display)

            pressed = cv2.waitKey(10) & 0xFF
            if pressed in (ord("q"), ord("Q"), 27):
                stop_event.set()
            if not samples and not frames:
                time.sleep(0.01)
    finally:
        try:
            subscriber.undeclare()
        except Exception:
            pass
        try:
            session.close()
        except Exception:
            pass
        cv2.destroyAllWindows()
        print("[INFO] Sensor receiver stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
