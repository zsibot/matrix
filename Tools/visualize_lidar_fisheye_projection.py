#!/usr/bin/env python3
"""Show four UeSim fisheye images with synchronized LiDAR and world bboxes.

    python3 Tools/visualize_lidar_fisheye_projection.py --check-only
    python3 Tools/visualize_lidar_fisheye_projection.py
    python3 Tools/visualize_lidar_fisheye_projection.py --camera-name surround_rear --lidar-name rear_lidar

Requires numpy, opencv-python, eclipse-zenoh and the sibling projection,
fisheye_surround_viewer.py and fisheye_bbox_overlay.py modules.
Default: 2x2 front/rear/left/right mosaic. Press S to save; Q/Esc to quit.
Uses UeSim's circular Kannala-Brandt renderer (including >180 degree FOV),
not perspective distortion or a rectified image. Config poses are in metres
and degrees; incoming LiDAR coordinates are ROS X-forward/Y-left/Z-up.
This visualizes existing calibration, it does not estimate new extrinsics.
BBox uses rt/dynamicinfo and world-coordinate odometry from config. Its JSON
has no Header, so bbox timing is receive-time approximate. --no-bbox disables it.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math

import visualize_lidar_camera_projection as common

np = common.np


@dataclass
class FisheyeCalibration:
    transform_camera_optical_from_lidar: "np.ndarray"
    fov_deg: float
    distortion: tuple[float, float, float, float]
    circle_scale: float
    principal_offset: tuple[float, float]
    expected_image_size: tuple[int, int]
    description: str
    synchronized: bool | None
    transform_base_from_lidar: "np.ndarray | None" = None

    @property
    def max_theta(self):
        return math.radians(self.fov_deg / 2.0)


def radial_polynomial(theta, coefficients):
    """UE EvaluateRadius, before its nonnegative clamp (validated monotonic)."""
    k1, k2, k3, k4 = coefficients
    t2 = theta * theta
    return theta * (1.0 + t2 * (k1 + t2 * (k2 + t2 * (k3 + t2 * k4))))


def validate_radial_model(coefficients, max_theta):
    # The renderer inverts this polynomial by bisection. Reject folds instead
    # of projecting a direction onto an unrelated inverse branch.
    k1, k2, k3, k4 = coefficients
    derivative = np.polynomial.Polynomial([1, 3*k1, 5*k2, 7*k3, 9*k4])
    candidates = [0.0, max_theta * max_theta]
    for root in derivative.deriv().roots():
        if abs(root.imag) < 1e-9 and 0 < root.real < candidates[1]:
            candidates.append(float(root.real))
    if min(derivative(np.asarray(candidates))) <= 0:
        raise ValueError("K1..K4 must give a strictly increasing radius across the fisheye FOV")


def load_calibration(args):
    with args.sensor_config.open(encoding="utf-8-sig") as stream:
        root = json.load(stream)
    sensors = common.sensor_map(root, args.sensor_config)
    camera_name, camera = common.select_sensor(sensors, args.camera_name, {"fisheye"}, "fisheye camera")
    lidar_name, lidar = common.select_sensor(sensors, args.lidar_name, common.LIDAR_TYPES, "LiDAR")
    if camera.get("enabled") is False or lidar.get("enabled") is False:
        raise ValueError("selected camera and LiDAR must be enabled")
    if camera.get("sensor_attach") != lidar.get("sensor_attach"):
        raise ValueError("camera and LiDAR need the same rigid sensor_attach")
    optical_from_body = np.eye(4)
    optical_from_body[:3, :3] = [[0, -1, 0], [0, 0, -1], [1, 0, 0]]
    transform = (
        optical_from_body
        @ np.linalg.inv(common.sensor_pose_in_ros_attach(camera))
        @ common.sensor_pose_in_ros_attach(lidar)
    )
    description = f"UeSim circular fisheye: {lidar_name} -> {camera_name} optical"
    if args.calibration_json:
        with args.calibration_json.open(encoding="utf-8-sig") as stream:
            override = json.load(stream)
        if any(key in override for key in ("intrinsics", "camera_matrix", "fx", "distortion", "distortion_coefficients")):
            raise ValueError("fisheye --calibration-json accepts extrinsics only; set fov and K1..K4 in --sensor-config")
        transform = override.get("T_camera_optical_lidar", override.get("matrix"))
        description += f"; extrinsic override: {args.calibration_json}"
    transform = common.validate_transform(transform, "T_camera_optical_lidar")
    coefficients = tuple(float(camera.get(f"K{i}", camera.get(f"k{i}", 0))) for i in range(1, 5))
    fov = float(camera.get("fov", 220))
    scale = float(camera.get("ImageCircleScale", 1))
    offset = (float(camera.get("PrincipalPointOffsetX", 0)), float(camera.get("PrincipalPointOffsetY", 0)))
    if not all(math.isfinite(v) for v in (*coefficients, fov, scale, *offset)):
        raise ValueError("fisheye parameters must be finite")
    if not 0 < fov <= 360:
        raise ValueError("fisheye fov must be in (0, 360]")
    # Reproduce the clamps in both UE CPU and GPU projection paths.
    fov = max(181.0, fov)
    scale = min(2.0, max(0.1, scale))
    size = (int(camera["width"]), int(camera["height"]))
    if min(size) < 2:
        raise ValueError("fisheye width and height must be at least 2")
    validate_radial_model(coefficients, math.radians(fov / 2))
    description += f"; FOV={fov:g} deg, K1..K4={coefficients}"
    if lidar.get("simulate_motion_distortion"):
        print("[WARN] LiDAR motion distortion is enabled; verify alignment at rest. This tool does not deskew points.")
    return (
        FisheyeCalibration(transform, fov, coefficients, scale, offset, size,
                           description, common.configured_sync_mode(root, args.sensor_config),
                           common.sensor_pose_in_ros_attach(lidar)),
        args.camera_key or common.zenoh_key(camera["topic"]),
        args.lidar_key or common.zenoh_key(lidar["topic"]),
    )


def image_geometry(calibration, width, height):
    center_x, center_y = (width - 1) / 2, (height - 1) / 2
    radius = max(1.0, min(center_x, center_y) * calibration.circle_scale)
    cx = center_x + calibration.principal_offset[0] * radius
    cy = center_y + calibration.principal_offset[1] * radius
    return radius, cx, cy


def intrinsics_for_image(calibration, width, height):
    radius, cx, cy = image_geometry(calibration, width, height)
    focal = radius / radial_polynomial(calibration.max_theta, calibration.distortion)
    return focal, focal, cx, cy


def project_optical_points(optical, calibration, width, height):
    """Return floating pixels, camera ranges, and visibility for Nx3 optical XYZ.

    atan2(hypot(x,y), z) preserves angles beyond 90 degrees. Camera range,
    rather than signed optical Z, orders occlusion even in the rear hemisphere.
    The exact rear axis at theta=pi has no unique azimuth and is excluded.
    """
    optical = np.asarray(optical, dtype=np.float64)
    if optical.ndim != 2 or optical.shape[1] != 3:
        raise ValueError("optical points must have shape (N, 3)")
    x, y, z = optical.T
    transverse = np.hypot(x, y)
    distance = np.hypot(transverse, z)
    theta = np.arctan2(transverse, z)
    fx, fy, cx, cy = intrinsics_for_image(calibration, width, height)
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        radial = radial_polynomial(theta, calibration.distortion)
        direction_x = np.divide(x, transverse, out=np.zeros_like(x), where=transverse > 0)
        direction_y = np.divide(y, transverse, out=np.zeros_like(y), where=transverse > 0)
        pixels = np.column_stack((cx + fx * radial * direction_x, cy + fy * radial * direction_y))
    visible = (
        np.all(np.isfinite(optical), axis=1) & np.all(np.isfinite(pixels), axis=1)
        & (distance > 1e-9) & (theta <= calibration.max_theta)
        & ~((transverse <= 1e-12 * distance) & (z < 0))
    )
    return pixels, distance, visible


def project_cloud(image_bgr, cloud, calibration, min_range_m, max_range_m,
                  point_radius, alpha, max_points, color_mode="adaptive",
                  transform_camera_optical_from_lidar=None):
    height, width = image_bgr.shape[:2]
    xyz = cloud.xyz_m[np.all(np.isfinite(cloud.xyz_m), axis=1)]
    finite_points = len(xyz)
    ranges = np.linalg.norm(xyz, axis=1)
    keep = (ranges >= min_range_m) & (ranges <= max_range_m)
    xyz, ranges = xyz[keep], ranges[keep]
    counts = (len(cloud.xyz_m), finite_points, len(xyz))
    transform = (calibration.transform_camera_optical_from_lidar
                 if transform_camera_optical_from_lidar is None
                 else transform_camera_optical_from_lidar)
    optical = xyz @ transform[:3, :3].T + transform[:3, 3]
    pixels, distance, visible = project_optical_points(optical, calibration, width, height)
    pixels = np.rint(pixels)
    radius, cx, cy = image_geometry(calibration, width, height)
    u, v = pixels.T
    visible &= ((u >= 0) & (u < width) & (v >= 0) & (v < height)
                & ((u-cx)**2 + (v-cy)**2 <= radius**2))
    u, v = pixels[visible].astype(np.int64).T
    yy, xx = np.ogrid[:height, :width]
    image_mask = (xx-cx)**2 + (yy-cy)**2 <= radius**2
    result, stats, intrinsics = common.render_projected_points(
        image_bgr, u, v, distance[visible], ranges[visible], counts,
        intrinsics_for_image(calibration, width, height), min_range_m,
        max_range_m, point_radius, alpha, max_points, color_mode, image_mask=image_mask,
    )
    return result, stats, intrinsics


def parse_args():
    parser = common.build_argument_parser()
    parser.description = __doc__
    parser.set_defaults(
        sensor_config=common.DEFAULT_SENSOR_CONFIG.parent / "sensors" / "config_surround4_airy_calibration_approx.json",
        camera_name="all", lidar_name="auto",
        save_dir=common.PROJECT_ROOT / "Saved" / "LidarFisheyeProjection",
    )
    parser.epilog = "--calibration-json overrides only T_camera_optical_lidar (4x4, metres); fisheye parameters come from --sensor-config."
    for action in parser._actions:
        if action.dest == "calibration_json":
            action.help = "override T_camera_optical_lidar only (4x4, metres)"
        elif action.dest == "camera_name":
            action.help = "camera name, or all for a 2x2 surround mosaic (default: all)"
        elif action.dest == "lidar_name":
            action.help = "LiDAR name, or auto: rear_lidar for surround_rear, front_lidar for others"
    parser.add_argument("--no-bbox", action="store_true", help="disable bbox subscription and overlay")
    parser.add_argument("--bbox-key", default="rt/dynamicinfo")
    parser.add_argument("--bbox-max-age", type=float, default=0.3, help="maximum bbox receive-time age/difference in seconds")
    parser.add_argument("--bbox-pose-max-gap", type=float, default=0.1, help="maximum odometry interpolation/extrapolation gap in seconds")
    parser.add_argument("--bbox-odom-key", help="world-coordinate nav_msgs/Odometry key; otherwise read from config")
    parser.add_argument("--bbox-odom-name", help="odometry sensor name in config")
    parser.add_argument("--bbox-pose-time-mode", choices=("auto", "header", "receive"), default="auto",
                        help="ego pose timing: auto prefers Header, falls back to receive time for large clock offsets")
    parser.add_argument("--bbox-odom-time-offset", type=float, default=0.0,
                        help="seconds added to odometry Headers before matching camera time")
    return parser.parse_args()


def main():
    from fisheye_surround_viewer import run
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
