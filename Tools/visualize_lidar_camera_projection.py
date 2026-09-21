#!/usr/bin/env python3
"""Display a synchronized UeSim LiDAR-to-camera projection live.

This tool subscribes only to a rigidly mounted camera and LiDAR. It accepts a
pair with identical ROS Header nanoseconds when available, otherwise the nearest
pair inside ``--max-time-diff``. It then applies one fixed camera-from-LiDAR
extrinsic. IMU, odometry and motion compensation are deliberately not part of
this projection path.

Press ``S`` to save the current frame and ``Q`` or ``Esc`` to exit.

Run from the source-tree or MATRiX release root:

    python3 Tools/visualize_lidar_camera_projection.py
    python3 Tools/visualize_lidar_camera_projection.py

Install dependencies with:

    python3 -m pip install numpy opencv-python eclipse-zenoh

The default calibration and topics come from the active ``config.json``. UeSim
publishes LiDAR points in ROS coordinates (X forward, Y left, Z up), in metres.
Perspective images use the configured horizontal FOV or pixel intrinsics and
the same Brown-Conrady distortion coefficients as UeSim. For a calibrated
physical pair, use ``--calibration-json``.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left
import json
import math
import signal
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

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


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def default_sensor_config() -> Path:
    """Support both the source tree (Scripts/) and MATRiX package (Tools/)."""
    candidates = (
        PROJECT_ROOT / "Content" / "model" / "config" / "config.json",
        PROJECT_ROOT
        / "UeSim"
        / "Content"
        / "model"
        / "config"
        / "config.json",
        PROJECT_ROOT
        / "Linux"
        / "UeSim"
        / "Content"
        / "model"
        / "config"
        / "config.json",
    )
    return next((path for path in candidates if path.is_file()), candidates[0])


DEFAULT_SENSOR_CONFIG = default_sensor_config()
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "Saved" / "LidarCameraProjection"
CAMERA_TYPES = {"rgb", "camera"}
LIDAR_TYPES = {"airy", "mid360", "lidar"}
ODOM_TYPES = {"odom", "odometry"}
IMU_TYPES = {"imu"}


@dataclass(frozen=True)
class PointField:
    name: str
    offset: int
    datatype: int
    count: int


@dataclass
class CameraFrame:
    stamp: float
    frame_id: str
    image_bgr: "np.ndarray"


@dataclass
class PointCloudFrame:
    stamp: float
    frame_id: str
    xyz_m: "np.ndarray"


@dataclass(frozen=True)
class RawFrame:
    stamp_ns: int
    payload: bytes

    @property
    def stamp(self) -> float:
        return self.stamp_ns * 1e-9


@dataclass
class PoseFrame:
    stamp: float
    position_world_m: "np.ndarray"
    quaternion_world_from_base_xyzw: "np.ndarray"
    linear_velocity_world_mps: "np.ndarray"
    angular_velocity_base_rps: "np.ndarray"


@dataclass
class ImuFrame:
    stamp: float
    quaternion_world_from_base_xyzw: "np.ndarray"
    angular_velocity_base_rps: "np.ndarray"


@dataclass
class Calibration:
    transform_camera_optical_from_lidar: "np.ndarray"
    transform_base_from_camera_body: "np.ndarray"
    transform_base_from_lidar: "np.ndarray"
    transform_base_from_odom: "np.ndarray"
    transform_base_from_imu: "np.ndarray"
    transform_optical_from_camera_body: "np.ndarray"
    dynamic_calibration_correction: "np.ndarray"
    horizontal_fov_deg: Optional[float]
    intrinsics: Optional[Tuple[float, float, float, float]]
    intrinsics_size: Optional[Tuple[int, int]]
    distortion: Tuple[float, float, float, float, float]
    expected_image_size: Optional[Tuple[int, int]]
    description: str
    synchronized: Optional[bool]


@dataclass
class ProjectionStats:
    source_points: int
    finite_points: int
    range_valid_points: int
    image_points: int
    visible_pixels: int


class CdrReader:
    """Minimal XCDR1 reader for the ROS 2 messages used here."""

    def __init__(self, data: bytes):
        if len(data) < 4:
            raise ValueError("CDR payload is shorter than its header")
        if data[:2] == b"\x00\x01":
            self.endian = "<"
        elif data[:2] == b"\x00\x00":
            self.endian = ">"
        else:
            raise ValueError(f"unsupported CDR encapsulation {data[:4].hex()}")
        self.data = data
        self.offset = 4

    def unpack(self, fmt: str, alignment: int):
        # XCDR alignment is relative to the byte after the 4-byte
        # encapsulation header, not to the start of the network payload.
        relative = self.offset - 4
        self.offset = 4 + ((relative + alignment - 1) & ~(alignment - 1))
        size = struct.calcsize(fmt)
        if self.offset + size > len(self.data):
            raise ValueError("CDR field exceeds payload length")
        value = struct.unpack_from(self.endian + fmt, self.data, self.offset)[0]
        self.offset += size
        return value

    def u8(self) -> int:
        return int(self.unpack("B", 1))

    def i32(self) -> int:
        return int(self.unpack("i", 4))

    def u32(self) -> int:
        return int(self.unpack("I", 4))

    def f64(self) -> float:
        return float(self.unpack("d", 8))

    def skip_f64(self, count: int) -> None:
        relative = self.offset - 4
        self.offset = 4 + ((relative + 7) & ~7)
        size = count * 8
        if self.offset + size > len(self.data):
            raise ValueError("CDR double array exceeds payload length")
        self.offset += size

    def string(self) -> str:
        size = self.u32()
        if self.offset + size > len(self.data):
            raise ValueError("CDR string exceeds payload length")
        raw = self.data[self.offset : self.offset + size]
        self.offset += size
        return raw.rstrip(b"\x00").decode("utf-8", errors="replace")

    def bytes(self) -> bytes:
        size = self.u32()
        if self.offset + size > len(self.data):
            raise ValueError("CDR byte sequence exceeds payload length")
        raw = self.data[self.offset : self.offset + size]
        self.offset += size
        return raw


def payload_bytes(payload) -> bytes:
    try:
        return bytes(payload)
    except TypeError:
        return payload.to_bytes()


def message_stamp(data: bytes) -> float:
    """Read only the common ROS Header timestamp without decoding the payload."""
    return message_stamp_ns(data) * 1e-9


def message_stamp_ns(data: bytes) -> int:
    """Read the ROS Header as an exact integer nanosecond value."""
    reader = CdrReader(data)
    return reader.i32() * 1_000_000_000 + reader.u32()


def read_f64_array(reader: CdrReader, count: int) -> "np.ndarray":
    return np.asarray([reader.f64() for _ in range(count)], dtype=np.float64)


def normalized_quaternion(quaternion_xyzw: "np.ndarray") -> "np.ndarray":
    quaternion = np.asarray(quaternion_xyzw, dtype=np.float64)
    norm = float(np.linalg.norm(quaternion))
    if quaternion.shape != (4,) or not math.isfinite(norm) or norm < 1e-12:
        raise ValueError("invalid zero or non-finite quaternion")
    return quaternion / norm


def quaternion_to_rotation(quaternion_xyzw: "np.ndarray") -> "np.ndarray":
    x, y, z, w = normalized_quaternion(quaternion_xyzw)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def rotation_to_quaternion(rotation: "np.ndarray") -> "np.ndarray":
    """Convert a proper 3x3 rotation matrix to an XYZW quaternion."""
    matrix = np.asarray(rotation, dtype=np.float64)
    trace = float(np.trace(matrix))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        quaternion = np.array(
            [
                (matrix[2, 1] - matrix[1, 2]) / scale,
                (matrix[0, 2] - matrix[2, 0]) / scale,
                (matrix[1, 0] - matrix[0, 1]) / scale,
                0.25 * scale,
            ]
        )
    else:
        index = int(np.argmax(np.diag(matrix)))
        if index == 0:
            scale = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
            quaternion = np.array(
                [
                    0.25 * scale,
                    (matrix[0, 1] + matrix[1, 0]) / scale,
                    (matrix[0, 2] + matrix[2, 0]) / scale,
                    (matrix[2, 1] - matrix[1, 2]) / scale,
                ]
            )
        elif index == 1:
            scale = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
            quaternion = np.array(
                [
                    (matrix[0, 1] + matrix[1, 0]) / scale,
                    0.25 * scale,
                    (matrix[1, 2] + matrix[2, 1]) / scale,
                    (matrix[0, 2] - matrix[2, 0]) / scale,
                ]
            )
        else:
            scale = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
            quaternion = np.array(
                [
                    (matrix[0, 2] + matrix[2, 0]) / scale,
                    (matrix[1, 2] + matrix[2, 1]) / scale,
                    0.25 * scale,
                    (matrix[1, 0] - matrix[0, 1]) / scale,
                ]
            )
    return normalized_quaternion(quaternion)


def quaternion_slerp(
    first_xyzw: "np.ndarray", second_xyzw: "np.ndarray", fraction: float
) -> "np.ndarray":
    first = normalized_quaternion(first_xyzw)
    second = normalized_quaternion(second_xyzw)
    dot = float(np.dot(first, second))
    if dot < 0.0:
        second, dot = -second, -dot
    dot = min(1.0, max(-1.0, dot))
    if dot > 0.9995:
        return normalized_quaternion(first + fraction * (second - first))
    angle = math.acos(dot)
    sine = math.sin(angle)
    return normalized_quaternion(
        math.sin((1.0 - fraction) * angle) / sine * first
        + math.sin(fraction * angle) / sine * second
    )


def quaternion_multiply(first_xyzw: "np.ndarray", second_xyzw: "np.ndarray") -> "np.ndarray":
    x1, y1, z1, w1 = first_xyzw
    x2, y2, z2, w2 = second_xyzw
    return normalized_quaternion(
        np.array(
            [
                w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
                w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            ]
        )
    )


def rotation_vector_quaternion(rotation_vector: "np.ndarray") -> "np.ndarray":
    angle = float(np.linalg.norm(rotation_vector))
    if angle < 1e-12:
        return normalized_quaternion(
            np.r_[0.5 * np.asarray(rotation_vector, dtype=np.float64), 1.0]
        )
    axis = np.asarray(rotation_vector, dtype=np.float64) / angle
    return np.r_[axis * math.sin(0.5 * angle), math.cos(0.5 * angle)]


def pose_matrix(position_m: "np.ndarray", quaternion_xyzw: "np.ndarray") -> "np.ndarray":
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = quaternion_to_rotation(quaternion_xyzw)
    transform[:3, 3] = position_m
    return transform


def parse_odometry(data: bytes, transform_base_from_odom: "np.ndarray") -> PoseFrame:
    """Decode nav_msgs/Odometry and return the reported base_link world pose."""
    reader = CdrReader(data)
    sec, nanosec = reader.i32(), reader.u32()
    reader.string()  # header.frame_id (normally odom)
    reader.string()  # child_frame_id (normally base_link)
    position_world_from_sensor = read_f64_array(reader, 3)
    quaternion_world_from_sensor = normalized_quaternion(read_f64_array(reader, 4))
    reader.skip_f64(36)  # pose covariance
    linear_velocity_base = read_f64_array(reader, 3)
    angular_velocity_base = read_f64_array(reader, 3)
    reader.skip_f64(36)  # twist covariance

    transform_world_from_sensor = pose_matrix(
        position_world_from_sensor, quaternion_world_from_sensor
    )
    transform_world_from_base = transform_world_from_sensor @ np.linalg.inv(
        transform_base_from_odom
    )
    quaternion_world_from_base = rotation_to_quaternion(
        transform_world_from_base[:3, :3]
    )
    linear_velocity_world = (
        transform_world_from_base[:3, :3] @ linear_velocity_base
    )
    values = np.r_[
        transform_world_from_base[:3, 3],
        linear_velocity_world,
        angular_velocity_base,
    ]
    if not np.all(np.isfinite(values)):
        raise ValueError("Odometry contains a non-finite pose or velocity")
    return PoseFrame(
        sec + nanosec * 1e-9,
        transform_world_from_base[:3, 3].copy(),
        quaternion_world_from_base,
        linear_velocity_world,
        angular_velocity_base,
    )


def parse_imu(data: bytes, transform_base_from_imu: "np.ndarray") -> ImuFrame:
    """Decode sensor_msgs/Imu and express orientation/gyro in base_link."""
    reader = CdrReader(data)
    sec, nanosec = reader.i32(), reader.u32()
    reader.string()
    quaternion_world_from_imu = normalized_quaternion(read_f64_array(reader, 4))
    reader.skip_f64(9)
    angular_velocity_imu = read_f64_array(reader, 3)
    reader.skip_f64(9)
    reader.skip_f64(3)  # linear acceleration
    reader.skip_f64(9)

    rotation_world_from_imu = quaternion_to_rotation(quaternion_world_from_imu)
    rotation_base_from_imu = transform_base_from_imu[:3, :3]
    rotation_world_from_base = rotation_world_from_imu @ rotation_base_from_imu.T
    angular_velocity_base = rotation_base_from_imu @ angular_velocity_imu
    if not np.all(np.isfinite(angular_velocity_base)):
        raise ValueError("IMU contains a non-finite angular velocity")
    return ImuFrame(
        sec + nanosec * 1e-9,
        rotation_to_quaternion(rotation_world_from_base),
        angular_velocity_base,
    )


def parse_compressed_image(data: bytes) -> CameraFrame:
    reader = CdrReader(data)
    sec, nanosec = reader.i32(), reader.u32()
    frame_id = reader.string()
    image_format = reader.string()
    encoded = reader.bytes()
    image = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"OpenCV cannot decode image format {image_format!r}")
    return CameraFrame(sec + nanosec * 1e-9, frame_id, image)


POINT_DTYPES = {
    1: "i1",  # INT8
    2: "u1",  # UINT8
    3: "i2",  # INT16
    4: "u2",  # UINT16
    5: "i4",  # INT32
    6: "u4",  # UINT32
    7: "f4",  # FLOAT32
    8: "f8",  # FLOAT64
}


def extract_point_field(
    raw: bytes,
    field: PointField,
    point_step: int,
    row_step: int,
    width: int,
    height: int,
    big_endian: bool,
) -> "np.ndarray":
    if field.datatype not in POINT_DTYPES or field.count != 1:
        raise ValueError(f"unsupported PointField {field.name!r}")
    dtype = np.dtype((">" if big_endian else "<") + POINT_DTYPES[field.datatype])
    required = (
        (height - 1) * row_step
        + (width - 1) * point_step
        + field.offset
        + dtype.itemsize
    )
    if (
        width <= 0
        or height <= 0
        or field.offset + dtype.itemsize > point_step
        or required > len(raw)
    ):
        raise ValueError("PointCloud2 shape, stride, or field offset is invalid")
    view = np.ndarray(
        (height, width),
        dtype=dtype,
        buffer=raw,
        offset=field.offset,
        strides=(row_step, point_step),
    )
    return np.asarray(view).reshape(-1).copy()


def parse_pointcloud2(data: bytes) -> PointCloudFrame:
    reader = CdrReader(data)
    sec, nanosec = reader.i32(), reader.u32()
    frame_id = reader.string()
    height, width = reader.u32(), reader.u32()
    field_count = reader.u32()
    if not 1 <= field_count <= 128:
        raise ValueError(f"invalid PointCloud2 field count {field_count}")
    fields: Dict[str, PointField] = {}
    for _ in range(field_count):
        name = reader.string()
        fields[name] = PointField(name, reader.u32(), reader.u8(), reader.u32())
    big_endian = bool(reader.u8())
    point_step, row_step = reader.u32(), reader.u32()
    raw = reader.bytes()
    reader.u8()  # is_dense
    if point_step <= 0 or row_step < width * point_step:
        raise ValueError("invalid PointCloud2 point_step or row_step")
    if not all(name in fields for name in ("x", "y", "z")):
        raise ValueError("PointCloud2 must contain x, y, and z")
    xyz = np.column_stack(
        [
            extract_point_field(
                raw, fields[name], point_step, row_step, width, height, big_endian
            )
            for name in ("x", "y", "z")
        ]
    ).astype(np.float64, copy=False)
    return PointCloudFrame(sec + nanosec * 1e-9, frame_id, xyz)


def rotation_matrix_rpy_deg(roll: float, pitch: float, yaw: float) -> "np.ndarray":
    """Return fixed-axis RPY rotation: Rz(yaw) @ Ry(pitch) @ Rx(roll)."""
    roll, pitch, yaw = np.deg2rad([roll, pitch, yaw])
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], np.float64)
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], np.float64)
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], np.float64)
    return rz @ ry @ rx


def sensor_pose_in_ros_attach(sensor: dict) -> "np.ndarray":
    """Reproduce BP_SpawnManager's config pose in the ROS-mirrored frame."""
    position = sensor.get("position", {})
    rotation = sensor.get("rotation", {})
    # BP uses MuJoCoToUERotation: UE(Pitch,Yaw,Roll)=(pitch,-yaw,-roll).
    # Mirroring the resulting UE transform back to ROS gives RPY(-r,-p,+y).
    roll = -float(rotation.get("roll", 0.0))
    pitch = -float(rotation.get("pitch", 0.0))
    yaw = float(rotation.get("yaw", 0.0))
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation_matrix_rpy_deg(roll, pitch, yaw)
    transform[:3, 3] = [
        float(position.get("x", 0.0)),
        float(position.get("y", 0.0)),
        float(position.get("z", 0.0)),
    ]
    return transform


def validate_transform(value, name: str) -> "np.ndarray":
    transform = np.asarray(value, dtype=np.float64)
    if transform.shape != (4, 4) or not np.all(np.isfinite(transform)):
        raise ValueError(f"{name} must be a finite 4x4 matrix")
    if not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-7):
        raise ValueError(f"{name} last row must be [0, 0, 0, 1]")
    rotation = transform[:3, :3]
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-3):
        raise ValueError(f"{name} rotation is not orthonormal")
    if not math.isclose(float(np.linalg.det(rotation)), 1.0, abs_tol=2e-3):
        raise ValueError(f"{name} rotation determinant must be +1")
    return transform


def sensor_map(config_root: dict, path: Path) -> dict:
    if isinstance(config_root.get("robot"), dict):
        sensors = config_root["robot"].get("sensors")
        if isinstance(sensors, dict):
            return sensors
    if isinstance(config_root.get("sensors"), dict):
        return config_root["sensors"]
    if config_root and all(isinstance(value, dict) for value in config_root.values()):
        return config_root
    raise ValueError(f"cannot find sensors in {path}")


def select_sensor(
    sensors: dict, requested: Optional[str], accepted_types: set[str], role: str
) -> Tuple[str, dict]:
    if requested:
        if requested not in sensors:
            raise ValueError(f"{role} {requested!r} is not in the sensor config")
        candidates = [requested]
    else:
        candidates = [
            name
            for name, value in sensors.items()
            if str(value.get("sensor_type", "")).lower() in accepted_types
        ]
    if not candidates:
        raise ValueError(
            f"no {role} in the sensor config; load and apply a camera/LiDAR scheme "
            "in UeSim first (see docs/Sensor_Schemes.md), or pass --sensor-config "
            "with a scheme file for an offline --check-only run"
        )
    if len(candidates) != 1:
        names = ", ".join(candidates)
        raise ValueError(f"expected one {role}, found {names}; select it explicitly")
    name = candidates[0]
    sensor = sensors[name]
    if str(sensor.get("sensor_type", "")).lower() not in accepted_types:
        raise ValueError(f"sensor {name!r} is not a supported {role}")
    return name, sensor


def select_optional_sensor(
    sensors: dict, requested: Optional[str], accepted_types: set[str], role: str
) -> Tuple[Optional[str], Optional[dict]]:
    if requested:
        if requested not in sensors:
            raise ValueError(f"{role} {requested!r} is not in the sensor config")
        name = requested
        sensor = sensors[name]
        if str(sensor.get("sensor_type", "")).lower() not in accepted_types:
            raise ValueError(f"sensor {name!r} is not a supported {role}")
        return name, sensor
    candidates = [
        name
        for name, value in sensors.items()
        if str(value.get("sensor_type", "")).lower() in accepted_types
    ]
    if len(candidates) > 1:
        raise ValueError(
            f"found multiple {role} sensors ({', '.join(candidates)}); select one explicitly"
        )
    if not candidates:
        return None, None
    return candidates[0], sensors[candidates[0]]


def zenoh_key(topic: str) -> str:
    topic = topic.strip()
    return topic if topic.startswith("rt/") else "rt" + (topic if topic.startswith("/") else "/" + topic)


def parse_intrinsics(
    value: dict,
) -> Tuple[Tuple[float, float, float, float], Optional[Tuple[int, int]]]:
    value = value.get("intrinsics", value)
    if "camera_matrix" in value:
        matrix = np.asarray(value["camera_matrix"], dtype=np.float64).reshape(3, 3)
        intrinsics = (
            float(matrix[0, 0]),
            float(matrix[1, 1]),
            float(matrix[0, 2]),
            float(matrix[1, 2]),
        )
    else:
        intrinsics = tuple(float(value[name]) for name in ("fx", "fy", "cx", "cy"))
    size = None
    if value.get("width") and value.get("height"):
        size = (int(value["width"]), int(value["height"]))
    if intrinsics[0] <= 0 or intrinsics[1] <= 0:
        raise ValueError("camera focal lengths must be positive")
    return intrinsics, size


def camera_config_intrinsics(
    camera: dict,
) -> Tuple[Optional[Tuple[float, float, float, float]], Optional[Tuple[int, int]]]:
    """Resolve optional UeSim perspective-intrinsic overrides.

    UeSim treats non-positive focal lengths and negative principal points as
    "derive from FOV/image size" sentinels. Keep the pure-sentinel case tied to
    the received image dimensions, but reproduce UeSim's fallback rules when
    any intrinsic is explicitly overridden.
    """
    width_value, height_value = camera.get("width"), camera.get("height")
    size = (
        (int(width_value), int(height_value))
        if width_value and height_value
        else None
    )
    values = {
        name: float(camera.get(name, default))
        for name, default in (("fx", 0.0), ("fy", 0.0), ("cx", -1.0), ("cy", -1.0))
    }
    has_override = (
        values["fx"] > 0.0
        or values["fy"] > 0.0
        or values["cx"] >= 0.0
        or values["cy"] >= 0.0
    )
    if not has_override:
        return None, None
    if size is None:
        if values["fx"] <= 0.0:
            raise ValueError("camera width/height are required when fx is derived from FOV")
        width = height = 1
    else:
        width, height = size
        if width <= 0 or height <= 0:
            raise ValueError("camera width and height must be positive")
    if values["fx"] > 0.0:
        fx = values["fx"]
    else:
        fov = float(camera.get("fov", 0.0))
        if not 0.0 < fov < 180.0:
            raise ValueError("camera needs a valid horizontal fov to derive fx")
        fx = width / (2.0 * math.tan(math.radians(fov) * 0.5))
    fy = values["fy"] if values["fy"] > 0.0 else fx
    cx = values["cx"] if values["cx"] >= 0.0 else (width - 1.0) * 0.5
    cy = values["cy"] if values["cy"] >= 0.0 else (height - 1.0) * 0.5
    if not all(math.isfinite(value) for value in (fx, fy, cx, cy)):
        raise ValueError("camera intrinsics must be finite")
    return (fx, fy, cx, cy), size


def parse_distortion(value: dict) -> Tuple[float, float, float, float, float]:
    """Return OpenCV-order Brown-Conrady coefficients (k1, k2, p1, p2, k3)."""
    raw = value.get("distortion_coefficients", value.get("distortion"))
    if raw is not None:
        coefficients = tuple(float(item) for item in raw)
        if len(coefficients) != 5:
            raise ValueError("distortion coefficients must contain k1,k2,p1,p2,k3")
    else:
        def coefficient(lower: str, upper: str) -> float:
            return float(value.get(lower, value.get(upper, 0.0)))

        coefficients = (
            coefficient("k1", "K1"),
            coefficient("k2", "K2"),
            coefficient("p1", "P1"),
            coefficient("p2", "P2"),
            coefficient("k3", "K3"),
        )
    if not all(math.isfinite(item) for item in coefficients):
        raise ValueError("camera distortion coefficients must be finite")
    return coefficients


def configured_sync_mode(config_root: dict, path: Path) -> Optional[bool]:
    """Read synchronization from a full config or the parent of a sensor scheme."""
    robot = config_root.get("robot")
    if isinstance(robot, dict) and "sensor_sync_mode" in robot:
        return bool(robot["sensor_sync_mode"])
    if "sensor_sync_mode" in config_root:
        return bool(config_root["sensor_sync_mode"])

    # A standalone .../config/sensors/<scheme>.json intentionally contains
    # sensors only. The active synchronization setting lives two levels up.
    parent_config = path.parent.parent / "config.json"
    if parent_config == path or not parent_config.is_file():
        return None
    try:
        with parent_config.open("r", encoding="utf-8") as stream:
            parent_root = json.load(stream)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    parent_robot = parent_root.get("robot", parent_root)
    if isinstance(parent_robot, dict) and "sensor_sync_mode" in parent_robot:
        return bool(parent_robot["sensor_sync_mode"])
    return None


def load_calibration(
    args: argparse.Namespace,
) -> Tuple[Calibration, str, str]:
    with args.sensor_config.open("r", encoding="utf-8") as stream:
        root = json.load(stream)
    sensors = sensor_map(root, args.sensor_config)
    camera_name, camera = select_sensor(sensors, args.camera_name, CAMERA_TYPES, "camera")
    lidar_name, lidar = select_sensor(sensors, args.lidar_name, LIDAR_TYPES, "LiDAR")
    camera_key = args.camera_key or zenoh_key(camera["topic"])
    lidar_key = args.lidar_key or zenoh_key(lidar["topic"])
    intrinsics, intrinsics_size = camera_config_intrinsics(camera)
    distortion = parse_distortion(camera)

    common_attach = camera.get("sensor_attach")
    if common_attach != lidar.get("sensor_attach"):
        raise ValueError(
            "camera and LiDAR have different sensor_attach values; "
            "a fixed extrinsic requires a common rigid base"
        )

    transform_base_from_camera = sensor_pose_in_ros_attach(camera)
    transform_base_from_lidar = sensor_pose_in_ros_attach(lidar)
    transform_base_from_odom = np.eye(4, dtype=np.float64)
    transform_base_from_imu = np.eye(4, dtype=np.float64)
    transform_optical_from_camera_body = np.eye(4, dtype=np.float64)
    transform_optical_from_camera_body[:3, :3] = np.array(
        [[0.0, -1.0, 0.0], [0.0, 0.0, -1.0], [1.0, 0.0, 0.0]],
        dtype=np.float64,
    )
    derived_transform = (
        transform_optical_from_camera_body
        @ np.linalg.inv(transform_base_from_camera)
        @ transform_base_from_lidar
    )
    derived_transform = validate_transform(
        derived_transform, "derived T_camera_optical_lidar"
    )

    if args.calibration_json:
        with args.calibration_json.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
        matrix = value.get("T_camera_optical_lidar", value.get("matrix"))
        if matrix is None:
            raise ValueError("calibration JSON needs T_camera_optical_lidar")
        transform = validate_transform(matrix, "T_camera_optical_lidar")
        dynamic_correction = transform @ np.linalg.inv(derived_transform)
        intrinsics, intrinsics_size = parse_intrinsics(value)
        distortion = parse_distortion(value)
        description = f"calibrated matrix and intrinsics from {args.calibration_json}"
    else:
        transform = derived_transform
        dynamic_correction = np.eye(4, dtype=np.float64)
        description = f"UeSim config poses: {lidar_name} -> {camera_name} optical"

    fov = float(camera["fov"]) if camera.get("fov") is not None else None
    if intrinsics is None and (fov is None or not 0.0 < fov < 180.0):
        raise ValueError("camera needs a valid horizontal fov or --calibration-json")
    expected_size = None
    if camera.get("width") and camera.get("height"):
        expected_size = (int(camera["width"]), int(camera["height"]))
    synchronized = configured_sync_mode(root, args.sensor_config)
    return (
        Calibration(
            transform_camera_optical_from_lidar=transform,
            transform_base_from_camera_body=transform_base_from_camera,
            transform_base_from_lidar=transform_base_from_lidar,
            transform_base_from_odom=transform_base_from_odom,
            transform_base_from_imu=transform_base_from_imu,
            transform_optical_from_camera_body=transform_optical_from_camera_body,
            dynamic_calibration_correction=dynamic_correction,
            horizontal_fov_deg=fov,
            intrinsics=intrinsics,
            intrinsics_size=intrinsics_size,
            distortion=distortion,
            expected_image_size=expected_size,
            description=description,
            synchronized=bool(synchronized) if synchronized is not None else None,
        ),
        camera_key,
        lidar_key,
    )


def append_timestamp_ordered(frames: deque, frame) -> None:
    """Keep the short sensor history ordered even if callbacks arrive out of order."""
    if not frames or frame.stamp >= frames[-1].stamp:
        if frames and math.isclose(frame.stamp, frames[-1].stamp, abs_tol=1e-9):
            frames[-1] = frame
        else:
            frames.append(frame)
        return
    ordered = [item for item in frames if not math.isclose(item.stamp, frame.stamp, abs_tol=1e-9)]
    ordered.append(frame)
    ordered.sort(key=lambda item: item.stamp)
    frames.clear()
    frames.extend(ordered[-frames.maxlen :])


def interpolation_indices(
    frames: deque, stamp: float, maximum_gap_s: float
) -> Tuple[int, int, float]:
    if not frames:
        raise ValueError("pose history is empty")
    stamps = [frame.stamp for frame in frames]
    upper = bisect_left(stamps, stamp)
    if upper == 0:
        delta = stamp - stamps[0]
        if abs(delta) > maximum_gap_s:
            raise ValueError(f"pose starts {abs(delta) * 1000.0:.1f} ms too late")
        return 0, 0, delta
    if upper == len(frames):
        delta = stamp - stamps[-1]
        if abs(delta) > maximum_gap_s:
            raise ValueError(f"pose ends {abs(delta) * 1000.0:.1f} ms too early")
        return len(frames) - 1, len(frames) - 1, delta
    before, after = upper - 1, upper
    span = stamps[after] - stamps[before]
    if span <= 0.0 or span > maximum_gap_s:
        raise ValueError(f"pose interpolation gap is {span * 1000.0:.1f} ms")
    return before, after, (stamp - stamps[before]) / span


def orientation_at(
    frames: deque, stamp: float, maximum_gap_s: float
) -> "np.ndarray":
    before, after, fraction_or_delta = interpolation_indices(
        frames, stamp, maximum_gap_s
    )
    if before != after:
        return quaternion_slerp(
            frames[before].quaternion_world_from_base_xyzw,
            frames[after].quaternion_world_from_base_xyzw,
            fraction_or_delta,
        )
    frame = frames[before]
    return quaternion_multiply(
        frame.quaternion_world_from_base_xyzw,
        rotation_vector_quaternion(frame.angular_velocity_base_rps * fraction_or_delta),
    )


def robot_pose_at(
    odometry: deque,
    imu: deque,
    stamp: float,
    maximum_gap_s: float,
) -> Tuple["np.ndarray", bool]:
    before, after, fraction_or_delta = interpolation_indices(
        odometry, stamp, maximum_gap_s
    )
    if before != after:
        first, second = odometry[before], odometry[after]
        position = first.position_world_m + fraction_or_delta * (
            second.position_world_m - first.position_world_m
        )
        quaternion = quaternion_slerp(
            first.quaternion_world_from_base_xyzw,
            second.quaternion_world_from_base_xyzw,
            fraction_or_delta,
        )
    else:
        frame = odometry[before]
        position = (
            frame.position_world_m
            + frame.linear_velocity_world_mps * fraction_or_delta
        )
        quaternion = quaternion_multiply(
            frame.quaternion_world_from_base_xyzw,
            rotation_vector_quaternion(
                frame.angular_velocity_base_rps * fraction_or_delta
            ),
        )

    used_imu = False
    if imu:
        try:
            quaternion = orientation_at(imu, stamp, maximum_gap_s)
            used_imu = True
        except ValueError:
            pass
    return pose_matrix(position, quaternion), used_imu


def motion_compensated_transform(
    calibration: Calibration,
    odometry: deque,
    imu: deque,
    camera_stamp: float,
    lidar_stamp: float,
    maximum_pose_gap_s: float,
) -> Tuple["np.ndarray", float, float, bool, "np.ndarray", float]:
    world_from_base_camera, camera_used_imu = robot_pose_at(
        odometry, imu, camera_stamp, maximum_pose_gap_s
    )
    world_from_base_lidar, lidar_used_imu = robot_pose_at(
        odometry, imu, lidar_stamp, maximum_pose_gap_s
    )
    transform = (
        calibration.dynamic_calibration_correction
        @ calibration.transform_optical_from_camera_body
        @ np.linalg.inv(calibration.transform_base_from_camera_body)
        @ np.linalg.inv(world_from_base_camera)
        @ world_from_base_lidar
        @ calibration.transform_base_from_lidar
    )
    relative_base_motion = np.linalg.inv(world_from_base_camera) @ world_from_base_lidar
    translation_m = float(np.linalg.norm(relative_base_motion[:3, 3]))
    cosine = (float(np.trace(relative_base_motion[:3, :3])) - 1.0) * 0.5
    rotation_deg = math.degrees(math.acos(min(1.0, max(-1.0, cosine))))
    base_yaw_deg = math.degrees(
        math.atan2(world_from_base_camera[1, 0], world_from_base_camera[0, 0])
    )
    return (
        validate_transform(transform, "motion-compensated transform"),
        translation_m,
        rotation_deg,
        camera_used_imu and lidar_used_imu,
        world_from_base_camera[:3, 3].copy(),
        base_yaw_deg,
    )


def intrinsics_for_image(
    calibration: Calibration, width: int, height: int
) -> Tuple[float, float, float, float]:
    if calibration.intrinsics is None:
        focal = width / (
            2.0 * math.tan(math.radians(calibration.horizontal_fov_deg) * 0.5)
        )
        return focal, focal, width * 0.5 - 0.5, height * 0.5 - 0.5
    fx, fy, cx, cy = calibration.intrinsics
    if calibration.intrinsics_size:
        source_width, source_height = calibration.intrinsics_size
        scale_x, scale_y = width / source_width, height / source_height
        fx, fy = fx * scale_x, fy * scale_y
        cx = (cx + 0.5) * scale_x - 0.5
        cy = (cy + 0.5) * scale_y - 0.5
    return fx, fy, cx, cy


def distort_normalized_points(
    x: "np.ndarray",
    y: "np.ndarray",
    coefficients: Tuple[float, float, float, float, float],
) -> Tuple["np.ndarray", "np.ndarray"]:
    """Apply the same Brown-Conrady model as UeSim's perspective camera."""
    if not any(coefficients):
        return x, y
    k1, k2, p1, p2, k3 = coefficients
    r2 = x * x + y * y
    radial = 1.0 + r2 * (k1 + r2 * (k2 + r2 * k3))
    xy2 = 2.0 * x * y
    distorted_x = x * radial + p1 * xy2 + p2 * (r2 + 2.0 * x * x)
    distorted_y = y * radial + p1 * (r2 + 2.0 * y * y) + p2 * xy2
    return distorted_x, distorted_y



def valid_distortion_branch(
    x: "np.ndarray", y: "np.ndarray",
    distorted_x: "np.ndarray", distorted_y: "np.ndarray",
    coefficients: Tuple[float, float, float, float, float],
    fx: float, fy: float,
) -> "np.ndarray":
    """Reject remote polynomial roots that fold off-camera rays into the image.

    The camera samples the central inverse-distortion branch for each output
    pixel. Forward Brown-Conrady alone is not one-to-one outside that domain:
    negative k3 can even bring grazing rays back to the image centre. Require
    the pixel's inverse ray to match the original ray, within 0.05 source pixels.
    This retains legitimate overscan rays near distorted image boundaries.
    """
    if not len(x) or not any(coefficients):
        return np.ones(len(x), dtype=bool)
    pixels = np.column_stack((distorted_x, distorted_y)).reshape(-1, 1, 2)
    inverse = cv2.undistortPointsIter(
        pixels, np.eye(3), np.asarray(coefficients, dtype=np.float64), None, None,
        (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 30, 1e-12),
    ).reshape(-1, 2)
    recovered_x, recovered_y = distort_normalized_points(
        inverse[:, 0], inverse[:, 1], coefficients
    )
    ray_error = np.hypot((inverse[:, 0] - x) * fx, (inverse[:, 1] - y) * fy)
    residual = np.hypot((recovered_x - distorted_x) * fx, (recovered_y - distorted_y) * fy)
    return np.isfinite(ray_error) & np.isfinite(residual) & (ray_error <= 0.05) & (residual <= 0.05)


def range_colors(
    ranges_m: "np.ndarray",
    minimum: float,
    maximum: float,
    logarithmic: bool,
) -> "np.ndarray":
    clipped = np.clip(ranges_m, minimum, maximum)
    if logarithmic:
        normalized = (np.log(clipped) - math.log(minimum)) / (
            math.log(maximum) - math.log(minimum)
        )
    else:
        normalized = (clipped - minimum) / (maximum - minimum)
    values = np.rint((1.0 - normalized) * 255.0).astype(np.uint8)
    return cv2.applyColorMap(values[:, None], cv2.COLORMAP_TURBO)[:, 0, :]


def draw_legend(
    image: "np.ndarray", minimum: float, maximum: float, logarithmic: bool
) -> None:
    height, width = image.shape[:2]
    bar_height = min(220, max(90, height // 3))
    if width < 180 or height < bar_height + 36:
        return
    x0, y0, bar_width = width - 112, 18, 18
    fractions = np.linspace(0.0, 1.0, bar_height)
    if logarithmic:
        ranges = minimum * np.power(maximum / minimum, fractions)
    else:
        ranges = minimum + fractions * (maximum - minimum)
    image[y0 : y0 + bar_height, x0 : x0 + bar_width] = range_colors(
        ranges, minimum, maximum, logarithmic
    )[:, None, :]
    cv2.rectangle(
        image,
        (x0 - 1, y0 - 1),
        (x0 + bar_width, y0 + bar_height),
        (255, 255, 255),
        1,
    )
    for fraction in (0.0, 0.5, 1.0):
        y = round(y0 + fraction * (bar_height - 1))
        if logarithmic:
            value = minimum * (maximum / minimum) ** fraction
        else:
            value = minimum + fraction * (maximum - minimum)
        cv2.putText(
            image,
            f"{value:.1f} m",
            (x0 + 25, y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )


def project_cloud(
    image_bgr: "np.ndarray",
    cloud: PointCloudFrame,
    calibration: Calibration,
    min_range_m: float,
    max_range_m: float,
    point_radius: int,
    alpha: float,
    max_points: int,
    color_mode: str = "adaptive",
    transform_camera_optical_from_lidar: Optional["np.ndarray"] = None,
) -> Tuple["np.ndarray", ProjectionStats, Tuple[float, float, float, float]]:
    height, width = image_bgr.shape[:2]
    fx, fy, cx, cy = intrinsics_for_image(calibration, width, height)
    source_points = len(cloud.xyz_m)
    xyz = cloud.xyz_m[np.all(np.isfinite(cloud.xyz_m), axis=1)]
    finite_points = len(xyz)
    ranges = np.linalg.norm(xyz, axis=1)
    valid_range = (ranges >= min_range_m) & (ranges <= max_range_m)
    xyz, ranges = xyz[valid_range], ranges[valid_range]
    range_valid_points = len(xyz)
    transform = (
        transform_camera_optical_from_lidar
        if transform_camera_optical_from_lidar is not None
        else calibration.transform_camera_optical_from_lidar
    )
    optical = xyz @ transform[:3, :3].T + transform[:3, 3]
    depth = optical[:, 2]
    forward = depth > 1e-6
    optical, depth, ranges = optical[forward], depth[forward], ranges[forward]
    x, y = optical[:, 0] / depth, optical[:, 1] / depth
    with np.errstate(over="ignore", invalid="ignore"):
        normalized_x, normalized_y = distort_normalized_points(x, y, calibration.distortion)
        pixel_x, pixel_y = np.rint(fx * normalized_x + cx), np.rint(fy * normalized_y + cy)
    # Reject non-finite and out-of-image values before casting to integers.
    inside = (np.isfinite(pixel_x) & np.isfinite(pixel_y)
              & (pixel_x >= 0) & (pixel_x < width) & (pixel_y >= 0) & (pixel_y < height))
    candidates = np.flatnonzero(inside)
    valid = valid_distortion_branch(
        x[candidates], y[candidates], normalized_x[candidates], normalized_y[candidates],
        calibration.distortion, fx, fy,
    )
    keep = candidates[valid]
    u, v = pixel_x[keep].astype(np.int64), pixel_y[keep].astype(np.int64)
    depth, ranges = depth[keep], ranges[keep]
    return render_projected_points(
        image_bgr, u, v, depth, ranges,
        (source_points, finite_points, range_valid_points),
        (fx, fy, cx, cy), min_range_m, max_range_m,
        point_radius, alpha, max_points, color_mode,
    )


def render_projected_points(
    image_bgr, u, v, depth, ranges, counts, intrinsics,
    min_range_m, max_range_m, point_radius, alpha, max_points, color_mode,
    image_mask=None,
):
    """Render projected pixels using positive depth/range to order occlusion."""
    height, width = image_bgr.shape[:2]
    source_points, finite_points, range_valid_points = counts
    image_points = len(depth)
    fx, fy, cx, cy = intrinsics
    # Nearest LiDAR return wins when several points hit the same image pixel.
    pixels = v * width + u
    order = np.lexsort((depth, pixels))
    sorted_pixels = pixels[order]
    first = (
        np.r_[True, sorted_pixels[1:] != sorted_pixels[:-1]]
        if len(order)
        else np.empty(0, bool)
    )
    keep = order[first]
    u, v, depth, ranges = u[keep], v[keep], depth[keep], ranges[keep]
    # Apply an optional display cap only after projection and the z-buffer.
    # Subsampling the raw 360-degree cloud first wastes most of the budget on
    # points outside the camera and makes object edges unnecessarily sparse.
    if max_points and len(depth) > max_points:
        sample = np.linspace(0, len(depth) - 1, max_points, dtype=np.int64)
        u, v, depth, ranges = (
            u[sample],
            v[sample],
            depth[sample],
            ranges[sample],
        )
    visible_pixels = len(depth)

    # Fixed 0.2-100 m colouring compresses typical scene distances into a
    # narrow part of the palette. In adaptive mode, ignore the outer 2% of
    # visible ranges and stretch the remaining distances across the full Turbo
    # palette. The projection and physical range filtering are unchanged.
    color_min, color_max = min_range_m, max_range_m
    logarithmic_colors = color_mode == "fixed"
    if color_mode == "adaptive" and len(ranges) >= 2:
        color_min, color_max = np.percentile(ranges, (2.0, 98.0))
        color_min = max(min_range_m, float(color_min))
        color_max = min(max_range_m, float(color_max))
        minimum_span = max(0.5, color_min * 0.05)
        if color_max - color_min < minimum_span:
            center = 0.5 * (color_min + color_max)
            color_min = max(min_range_m, center - minimum_span * 0.5)
            color_max = min(max_range_m, center + minimum_span * 0.5)
        if color_max <= color_min:
            color_min, color_max = min_range_m, max_range_m
            logarithmic_colors = True
    colors = (
        range_colors(ranges, color_min, color_max, logarithmic_colors)
        if len(ranges)
        else np.empty((0, 3), np.uint8)
    )

    overlay = image_bgr.copy()
    painted = np.zeros((height, width), dtype=bool)
    if point_radius == 0:
        overlay[v, u] = colors
        painted[v, u] = True
    elif len(depth):
        expanded_depth = np.full((height, width), np.inf)
        expanded_colors = np.zeros_like(image_bgr)
        for dy in range(-point_radius, point_radius + 1):
            for dx in range(-point_radius, point_radius + 1):
                if dx * dx + dy * dy > point_radius * point_radius:
                    continue
                target_x, target_y = u + dx, v + dy
                valid = (
                    (target_x >= 0)
                    & (target_x < width)
                    & (target_y >= 0)
                    & (target_y < height)
                )
                target_x, target_y = target_x[valid], target_y[valid]
                target_depth, target_colors = depth[valid], colors[valid]
                nearer = target_depth < expanded_depth[target_y, target_x]
                expanded_depth[target_y[nearer], target_x[nearer]] = target_depth[
                    nearer
                ]
                expanded_colors[target_y[nearer], target_x[nearer]] = target_colors[
                    nearer
                ]
        painted = np.isfinite(expanded_depth)
        overlay[painted] = expanded_colors[painted]
    if image_mask is not None:
        overlay[~image_mask] = image_bgr[~image_mask]
    # Avoid a second full-resolution allocation/blend in the common opaque case.
    if alpha >= 1.0:
        result = overlay
    elif alpha <= 0.0:
        result = image_bgr.copy()
    else:
        result = cv2.addWeighted(overlay, alpha, image_bgr, 1.0 - alpha, 0.0)
    draw_legend(result, color_min, color_max, logarithmic_colors)
    stats = ProjectionStats(
        source_points,
        finite_points,
        range_valid_points,
        image_points,
        visible_pixels,
    )
    return result, stats, (fx, fy, cx, cy)


def exact_synchronized_pair(
    cameras: deque[RawFrame], clouds: deque[RawFrame]
) -> Optional[Tuple[RawFrame, RawFrame]]:
    if not cameras or not clouds:
        return None

    # ROS Header has no sequence field. In synchronized UeSim mode the canonical
    # integer timestamp is the cross-sensor frame identity, so never substitute a
    # merely nearby frame. Doing so creates convincing but geometrically invalid
    # overlays while the robot rotates.
    cameras_by_stamp = {item.stamp_ns: item for item in cameras}
    clouds_by_stamp = {item.stamp_ns: item for item in clouds}
    common_stamps = cameras_by_stamp.keys() & clouds_by_stamp.keys()
    if not common_stamps:
        return None
    stamp_ns = max(common_stamps)
    return cameras_by_stamp[stamp_ns], clouds_by_stamp[stamp_ns]


def synchronized_pair(
    cameras: deque[RawFrame],
    clouds: deque[RawFrame],
    maximum_difference_ns: int,
) -> Optional[Tuple[RawFrame, RawFrame]]:
    """Prefer an exact Header pair, then the newest pair inside the tolerance."""
    exact = exact_synchronized_pair(cameras, clouds)
    if exact is not None or maximum_difference_ns <= 0:
        return exact
    candidates = [
        (camera, cloud)
        for camera in cameras
        for cloud in clouds
        if abs(camera.stamp_ns - cloud.stamp_ns) <= maximum_difference_ns
    ]
    if not candidates:
        return None
    # Prefer the newest acquisition edge; absolute delta breaks ties.
    return max(
        candidates,
        key=lambda pair: (
            min(pair[0].stamp_ns, pair[1].stamp_ns),
            -abs(pair[0].stamp_ns - pair[1].stamp_ns),
        ),
    )


def consume_synchronized_pair(
    cameras: deque[RawFrame],
    clouds: deque[RawFrame],
    camera_stamp_ns: int,
    cloud_stamp_ns: Optional[int] = None,
) -> None:
    """Remove a used pair and every older packet so it cannot be reused."""
    if cloud_stamp_ns is None:
        cloud_stamp_ns = camera_stamp_ns
    remaining_cameras = [item for item in cameras if item.stamp_ns > camera_stamp_ns]
    remaining_clouds = [item for item in clouds if item.stamp_ns > cloud_stamp_ns]
    cameras.clear()
    cameras.extend(remaining_cameras)
    clouds.clear()
    clouds.extend(remaining_clouds)


def build_zenoh_config(args: argparse.Namespace):
    config = zenoh.Config()
    config.insert_json5("mode", json.dumps("client"))
    config.insert_json5("connect/endpoints", json.dumps([args.connect]))
    config.insert_json5("scouting/multicast/enabled", "false")
    return config


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--sensor-config", type=Path, default=DEFAULT_SENSOR_CONFIG)
    parser.add_argument("--camera-name", help="camera name when the config has more than one")
    parser.add_argument("--lidar-name", help="LiDAR name when the config has more than one")
    parser.add_argument("--odom-name", help=argparse.SUPPRESS)
    parser.add_argument("--imu-name", help=argparse.SUPPRESS)
    parser.add_argument("--camera-key", help="override the camera Zenoh key")
    parser.add_argument("--lidar-key", help="override the LiDAR Zenoh key")
    parser.add_argument("--odom-key", help=argparse.SUPPRESS)
    parser.add_argument("--imu-key", help=argparse.SUPPRESS)
    parser.add_argument(
        "--calibration-json",
        type=Path,
        help="calibrated T_camera_optical_lidar and intrinsics",
    )
    parser.add_argument(
        "--connect", default="tcp/127.0.0.1:7447", help="Zenoh router endpoint"
    )
    parser.add_argument(
        "--max-time-diff",
        type=float,
        default=0.0,
        help=(
            "maximum camera/LiDAR Header difference in seconds after exact pairing "
            "fails (default: 0, exact nanoseconds; try 0.005 only for legacy data)"
        ),
    )
    parser.add_argument(
        "--pose-max-gap",
        type=float,
        default=0.05,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--camera-time-offset-ms",
        type=float,
        default=0.0,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-motion-compensation",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="seconds to wait for the first synchronized pair",
    )
    parser.add_argument(
        "--overlay-timeout",
        type=float,
        default=0.35,
        help="clear stale LiDAR points after this many seconds (default: 0.35)",
    )
    parser.add_argument(
        "--min-range", type=float, default=0.2, help="nearest LiDAR range in metres"
    )
    parser.add_argument(
        "--max-range", type=float, default=100.0, help="farthest LiDAR range in metres"
    )
    parser.add_argument(
        "--color-mode",
        choices=("adaptive", "fixed"),
        default="adaptive",
        help="adaptive maximizes live contrast; fixed preserves one global scale",
    )
    parser.add_argument(
        "--point-radius",
        type=int,
        default=2,
        help="rendered point radius in pixels (default: 2; 0 is one physical pixel)",
    )
    parser.add_argument(
        "--alpha", type=float, default=1.0, help="point overlay opacity"
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=16000,
        help="maximum displayed image points (default: 16000; 0 keeps every point)",
    )
    parser.add_argument(
        "--window-width",
        type=int,
        default=1280,
        help="initial display width; 0 keeps the camera resolution",
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory used when S is pressed",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="print calibration and exit without Zenoh",
    )
    return parser


def parse_args() -> argparse.Namespace:
    return build_argument_parser().parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if (
        args.max_time_diff < 0
        or args.pose_max_gap <= 0
        or args.timeout <= 0
        or args.overlay_timeout <= 0
    ):
        raise ValueError(
            "--max-time-diff must be nonnegative; pose/timeout values must be positive"
        )
    if abs(args.camera_time_offset_ms) > 500.0:
        raise ValueError("--camera-time-offset-ms must be between -500 and 500")
    if not 0 < args.min_range < args.max_range:
        raise ValueError("require 0 < --min-range < --max-range")
    if args.point_radius < 0 or args.max_points < 0:
        raise ValueError("--point-radius and --max-points cannot be negative")
    if args.window_width < 0:
        raise ValueError("--window-width cannot be negative")
    if not 0 <= args.alpha <= 1:
        raise ValueError("--alpha must be between 0 and 1")


def main(
    args=None, *, calibration_loader=load_calibration,
    projector=project_cloud, image_intrinsics=intrinsics_for_image,
) -> int:
    args = parse_args() if args is None else args
    if np is None or cv2 is None:
        print("[ERROR] missing dependency: install numpy and opencv-python")
        return 2
    try:
        validate_args(args)
        calibration, camera_key, lidar_key = calibration_loader(args)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}")
        return 2

    print(f"[INFO] camera: {camera_key}")
    print(f"[INFO] LiDAR:  {lidar_key}")
    print(f"[INFO] calibration: {calibration.description}")
    print("[INFO] T_camera_optical_lidar =")
    print(
        np.array2string(
            calibration.transform_camera_optical_from_lidar,
            precision=9,
            suppress_small=True,
        )
    )
    if calibration.expected_image_size:
        expected_width, expected_height = calibration.expected_image_size
        expected_intrinsics = image_intrinsics(
            calibration, expected_width, expected_height
        )
        print(
            "[INFO] camera model: "
            f"{expected_width}x{expected_height} "
            f"K=({expected_intrinsics[0]:.6f},{expected_intrinsics[1]:.6f},"
            f"{expected_intrinsics[2]:.6f},{expected_intrinsics[3]:.6f}) "
            f"D={calibration.distortion}"
        )
    if calibration.synchronized is False:
        print("[ERROR] sensor_sync_mode must be true for exact rigid-sensor projection")
        return 2
    if calibration.synchronized is None:
        print(
            "[WARN] sensor_sync_mode is not present in the supplied sensor scheme "
            "or its parent config; relying on synchronized Header timestamps"
        )
    pairing_description = (
        "exact Header nanoseconds only"
        if args.max_time_diff == 0.0
        else (
            "prefer exact Header; otherwise nearest within "
            f"{args.max_time_diff * 1000.0:.3f} ms"
        )
    )
    print(f"[INFO] pairing: {pairing_description}; transform: fixed extrinsic only")
    if args.check_only:
        return 0
    if zenoh is None:
        print("[ERROR] missing dependency: install eclipse-zenoh")
        return 2

    stop = threading.Event()
    lock = threading.Lock()
    raw_samples: Dict[str, deque[bytes]] = {
        "camera": deque(maxlen=8),
        "lidar": deque(maxlen=8),
    }
    camera_packets: deque[RawFrame] = deque(maxlen=16)
    cloud_packets: deque[RawFrame] = deque(maxlen=16)
    cameras: deque[CameraFrame] = deque(maxlen=2)
    input_stamps: Dict[str, deque[float]] = {
        "camera": deque(maxlen=32),
        "lidar": deque(maxlen=32),
    }

    def request_stop(_signum=None, _frame=None) -> None:
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    def callback(kind: str):
        def receive(sample) -> None:
            with lock:
                raw_samples[kind].append(payload_bytes(sample.payload))

        return receive

    subscribers = []
    session = None
    try:
        session = zenoh.open(build_zenoh_config(args))
        subscribers.append(session.declare_subscriber(camera_key, callback("camera")))
        subscribers.append(session.declare_subscriber(lidar_key, callback("lidar")))
    except Exception as error:
        for resource in subscribers:
            try:
                resource.undeclare()
            except Exception:
                pass
        if session is not None:
            session.close()
        print(f"[ERROR] cannot connect or subscribe: {error}")
        return 3

    window_name = "UeSim LiDAR -> Camera Projection"
    try:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    except cv2.error as error:
        for resource in subscribers:
            resource.undeclare()
        session.close()
        print(f"[ERROR] cannot create an OpenCV window: {error}")
        return 4

    print(
        f"[INFO] waiting up to {args.timeout:.1f}s for a synchronized camera/LiDAR pair; "
        "S saves, Q/Esc exits"
    )
    startup_deadline = time.monotonic() + args.timeout
    first_pair_received = False
    first_frame_displayed = False
    last_camera_stamp_ns: Optional[int] = None
    last_result: Optional["np.ndarray"] = None
    input_counts = {"camera": 0, "lidar": 0}
    latest_stamp_ns: Dict[str, Optional[int]] = {"camera": None, "lidar": None}
    status_started = time.monotonic()
    status_frames = 0
    display_fps = 0.0
    previous_display_time: Optional[float] = None
    last_projection_wall_time: Optional[float] = None
    overlay_cleared = True
    resolution_warning_printed = False
    geometry_warning_last_print = 0.0
    waiting_status_last_update = 0.0
    exit_code = 0

    def show_waiting_status() -> None:
        nonlocal waiting_status_last_update, last_result
        canvas = np.full((360, 760, 3), 28, dtype=np.uint8)
        camera_stamp = latest_stamp_ns["camera"]
        lidar_stamp = latest_stamp_ns["lidar"]
        lines = [
            "UeSim LiDAR -> Camera Projection",
            (
                "Waiting for an exact camera/LiDAR Header pair..."
                if args.max_time_diff == 0.0
                else "Waiting for a synchronized camera/LiDAR Header pair..."
            ),
            f"camera packets: {input_counts['camera']}  key: {camera_key}",
            f"LiDAR packets:  {input_counts['lidar']}  key: {lidar_key}",
            f"camera stamp: {camera_stamp if camera_stamp is not None else '-'}",
            f"LiDAR stamp:  {lidar_stamp if lidar_stamp is not None else '-'}",
        ]
        if camera_stamp is not None and lidar_stamp is not None:
            lines.append(f"latest Header delta: {(camera_stamp - lidar_stamp) / 1e6:+.3f} ms")
        for index, line in enumerate(lines):
            cv2.putText(
                canvas,
                line,
                (24, 48 + index * 44),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62 if index else 0.78,
                (230, 230, 230),
                1 if index else 2,
                cv2.LINE_AA,
            )
        cv2.imshow(window_name, canvas)
        last_result = canvas
        waiting_status_last_update = time.monotonic()

    # namedWindow alone may not map a visible window on Linux. Present an
    # explicit status frame before the first sensor packet arrives.
    show_waiting_status()
    cv2.waitKey(1)
    try:
        while not stop.is_set():
            with lock:
                pending = {
                    kind: list(samples) for kind, samples in raw_samples.items()
                }
                for samples in raw_samples.values():
                    samples.clear()
            for kind, samples in pending.items():
                for raw in samples:
                    try:
                        stamp_ns = message_stamp_ns(raw)
                        input_stamps[kind].append(stamp_ns * 1e-9)
                        input_counts[kind] += 1
                        latest_stamp_ns[kind] = stamp_ns
                        if kind == "camera":
                            camera_packets.append(RawFrame(stamp_ns, raw))
                        elif kind == "lidar":
                            cloud_packets.append(RawFrame(stamp_ns, raw))
                    except (ValueError, struct.error) as error:
                        print(f"[WARN] ignored invalid {kind} message: {error}")
            candidate = synchronized_pair(
                camera_packets,
                cloud_packets,
                round(args.max_time_diff * 1e9),
            )
            if (
                candidate
                and candidate[0].stamp_ns != last_camera_stamp_ns
            ):
                camera_packet, cloud_packet = candidate
                consume_synchronized_pair(
                    camera_packets,
                    cloud_packets,
                    camera_packet.stamp_ns,
                    cloud_packet.stamp_ns,
                )
                try:
                    # Decode only the selected pair. Older queued compressed
                    # frames are intentionally skipped to keep latency bounded.
                    camera = parse_compressed_image(camera_packet.payload)
                    cloud = parse_pointcloud2(cloud_packet.payload)
                    cameras.append(camera)
                    result, stats, intrinsics = projector(
                        camera.image_bgr,
                        cloud,
                        calibration,
                        args.min_range,
                        args.max_range,
                        args.point_radius,
                        args.alpha,
                        args.max_points,
                        args.color_mode,
                        transform_camera_optical_from_lidar=(
                            calibration.transform_camera_optical_from_lidar
                        ),
                    )
                except (ValueError, struct.error) as error:
                    last_camera_stamp_ns = camera_packet.stamp_ns
                    print(f"[WARN] ignored invalid synchronized pair: {error}")
                    continue
                last_camera_stamp_ns = camera_packet.stamp_ns
                first_pair_received = True
                now = time.monotonic()
                elapsed = max(now - status_started, 1e-6)
                status_fps = (status_frames + 1) / elapsed
                if previous_display_time is not None:
                    instant_fps = 1.0 / max(now - previous_display_time, 1e-6)
                    display_fps = (
                        instant_fps
                        if display_fps == 0.0
                        else 0.8 * display_fps + 0.2 * instant_fps
                    )
                previous_display_time = now
                last_projection_wall_time = now if stats.image_points else None
                overlay_cleared = not bool(stats.image_points)
                overlay_status = (
                    f"sync={'exact' if camera_packet.stamp_ns == cloud_packet.stamp_ns else 'nearest'} "
                    f"dt={(camera_packet.stamp_ns - cloud_packet.stamp_ns) / 1e6:+.3f}ms  "
                    f"projected={stats.image_points}  "
                    f"visible={stats.visible_pixels}  fps={display_fps:.1f}"
                    if stats.image_points
                    else (
                        "synchronized pair received - no LiDAR points project into the image"
                    )
                )
                cv2.putText(
                    result,
                    overlay_status,
                    (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                # Always show a valid synchronized camera frame. Previously
                # imshow was incorrectly conditional on projected point count,
                # making calibration failures look like a dead subscriber.
                cv2.imshow(window_name, result)
                last_result = result
                status_frames += 1
                if not first_frame_displayed:
                    if args.window_width:
                        display_height = round(
                            result.shape[0] * args.window_width / result.shape[1]
                        )
                        cv2.resizeWindow(window_name, args.window_width, display_height)
                    first_frame_displayed = True
                actual_size = (camera.image_bgr.shape[1], camera.image_bgr.shape[0])
                if (
                    not resolution_warning_printed
                    and calibration.expected_image_size
                    and actual_size != calibration.expected_image_size
                ):
                    print(
                        f"[WARN] received {actual_size[0]}x{actual_size[1]}, "
                        f"config declares {calibration.expected_image_size[0]}x"
                        f"{calibration.expected_image_size[1]}"
                    )
                    resolution_warning_printed = True
                if not stats.image_points and now - geometry_warning_last_print >= 1.0:
                    print(
                        "[WARN] no LiDAR points project into the image; verify "
                        "sensor names and calibration"
                    )
                    geometry_warning_last_print = now
                if elapsed >= 1.0:
                    fx, fy, cx, cy = intrinsics

                    def input_rate(kind: str) -> float:
                        stamps = input_stamps[kind]
                        duration = stamps[-1] - stamps[0] if len(stamps) >= 2 else 0.0
                        return (len(stamps) - 1) / duration if duration > 0.0 else 0.0

                    print(
                        f"[FRAME] display={status_fps:.1f}fps "
                        f"input={input_rate('camera'):.1f}/{input_rate('lidar'):.1f}Hz "
                        f"sync_ns={camera_packet.stamp_ns} "
                        f"dt_ms={(camera_packet.stamp_ns - cloud_packet.stamp_ns) / 1e6:+.3f} "
                        f"cloud={stats.source_points} projected={stats.image_points} "
                        f"visible={stats.visible_pixels} "
                        f"K=({fx:.2f},{fy:.2f},{cx:.2f},{cy:.2f})"
                    )
                    status_started = now
                    status_frames = 0

            if not first_pair_received and time.monotonic() - waiting_status_last_update >= 0.25:
                show_waiting_status()

            # imshow keeps the previous composite until another image replaces
            # it. If synchronized input stalls, explicitly replace that stale
            # composite with the newest clean camera frame.
            now = time.monotonic()
            if (
                first_frame_displayed
                and not overlay_cleared
                and last_projection_wall_time is not None
                and now - last_projection_wall_time >= args.overlay_timeout
                and cameras
            ):
                clean_frame = cameras[-1].image_bgr.copy()
                cv2.putText(
                    clean_frame,
                    "LiDAR overlay expired - waiting for synchronized cloud",
                    (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow(window_name, clean_frame)
                last_result = clean_frame
                overlay_cleared = True

            if not first_pair_received and time.monotonic() >= startup_deadline:
                camera_count = input_counts["camera"]
                lidar_count = input_counts["lidar"]
                if camera_count == 0 and lidar_count == 0:
                    reason = "received neither topic; start UeSim and its embedded Zenoh router"
                elif camera_count == 0:
                    reason = f"received LiDAR={lidar_count} but no camera packets"
                elif lidar_count == 0:
                    reason = f"received camera={camera_count} but no LiDAR packets"
                else:
                    camera_stamp = latest_stamp_ns["camera"]
                    lidar_stamp = latest_stamp_ns["lidar"]
                    delta_ms = (
                        (camera_stamp - lidar_stamp) / 1e6
                        if camera_stamp is not None and lidar_stamp is not None
                        else float("nan")
                    )
                    reason = (
                        f"received camera={camera_count}, LiDAR={lidar_count}, but no exact "
                        f"Header match; latest delta={delta_ms:+.3f} ms"
                    )
                print(f"[ERROR] timed out: {reason}")
                if camera_packets and cloud_packets:
                    nearest_camera, nearest_lidar = min(
                        (
                            (camera_packet.stamp_ns, cloud_packet.stamp_ns)
                            for camera_packet in camera_packets
                            for cloud_packet in cloud_packets
                        ),
                        key=lambda pair: abs(pair[0] - pair[1]),
                    )
                    print(
                        "[ERROR] nearest buffered Header delta="
                        f"{(nearest_camera - nearest_lidar) / 1e6:+.3f} ms "
                        f"camera_ns={nearest_camera} lidar_ns={nearest_lidar}"
                    )
                exit_code = 5
                break

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                stop.set()
            elif key in (ord("s"), ord("S")) and last_result is not None:
                args.save_dir.mkdir(parents=True, exist_ok=True)
                output = args.save_dir / time.strftime(
                    "lidar_camera_projection_%Y%m%d_%H%M%S.png"
                )
                if cv2.imwrite(str(output), last_result):
                    print(f"[INFO] saved {output.resolve()}")
                else:
                    print(f"[WARN] OpenCV could not write {output}")
            if not any(pending.values()):
                time.sleep(0.003)
    finally:
        for resource in subscribers:
            try:
                resource.undeclare()
            except Exception:
                pass
        try:
            session.close()
        except Exception:
            pass
        cv2.destroyAllWindows()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
