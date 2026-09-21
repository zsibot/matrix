"""ROS-world bbox geometry and curved wireframes for the fisheye viewer."""
from collections import deque
from dataclasses import dataclass, replace
import json
import math

import numpy as np

import visualize_lidar_camera_projection as common
import visualize_lidar_fisheye_projection as fish

EDGES = ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))
COLORS = {"vehicle": (255,166,88), "human": (87,186,242), "static": (160,220,120)}


@dataclass
class Box:
    label: str
    category: str
    corners: np.ndarray


def decode_boxes(payload):
    """Accept the recorder's actor-keyed, nested and double-encoded JSON."""
    boxes = []
    invalid = 0

    def visit(value, name="", category="unknown", depth=0):
        nonlocal invalid
        if depth > 16:
            raise ValueError("bbox JSON nesting exceeds 16")
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except ValueError:
                return
            visit(decoded, name, category, depth+1)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                visit(item, name or str(i), category, depth+1)
        elif isinstance(value, dict):
            category = str(value.get("category", value.get("Category", value.get("type", value.get("class", category))))).lower()
            name = str(value.get("label", value.get("name", value.get("id", name))))
            if "corners" in value or ("center" in value and "extent" in value):
                try:
                    if value.get("unit", "m") != "m" or value.get("coordinate_system", "ROS").upper() != "ROS":
                        raise ValueError("expected ROS world metres")
                    corners = np.asarray([[p[a] for a in "xyz"] for p in value["corners"]], dtype=float)
                    if corners.shape != (8,3) or not np.isfinite(corners).all():
                        raise ValueError("bbox requires eight finite world corners")
                    boxes.append(Box(name, category, corners))
                except (KeyError, ValueError, TypeError, AttributeError):
                    invalid += 1
                return
            for key, item in value.items():
                if key in ("velocity", "speed", "category", "Category", "type", "class"):
                    continue
                wrapper = key in ("bbox", "bboxes", "objects", "actors", "dynamicinfo", "data")
                grouped = key.lower() in ("vehicle", "human", "static")
                visit(item, name if wrapper or grouped else key,
                      key.lower() if grouped else category, depth+1)

    visit(json.loads(payload.decode("utf-8").strip("\x00 \r\n\t")))
    return boxes, invalid


def optical_from_world(calibration, world_from_base):
    return (calibration.transform_camera_optical_from_lidar
            @ np.linalg.inv(calibration.transform_base_from_lidar)
            @ np.linalg.inv(world_from_base))


def draw_boxes(image, boxes, calibration, transform):
    """Sample 3D edges before projection; never join across invalid FOV sections."""
    cv2 = common.cv2
    height, width = image.shape[:2]
    overlay = image.copy()
    visible_boxes = 0
    fractions = np.linspace(0, 1, 97)[:, None]
    for box in boxes:
        optical = box.corners @ transform[:3,:3].T + transform[:3,3]
        color = COLORS.get(box.category, (195,185,175))
        anchors = []
        for a, b in EDGES:
            points = optical[a] + fractions * (optical[b] - optical[a])
            pixels, _, valid = fish.project_optical_points(points, calibration, width, height)
            # Discontinuities near the optical centre must not draw a chord.
            connected = valid[:-1] & valid[1:]
            connected &= np.linalg.norm(np.diff(pixels,axis=0),axis=1) <= .15*min(width,height)
            indices = np.flatnonzero(connected)
            if not len(indices):
                continue
            # Batch contiguous samples as polylines instead of issuing a Python
            # drawing call for every tiny segment (four cameras share one UI).
            for group in np.split(indices,np.flatnonzero(np.diff(indices)!=1)+1):
                curve = np.rint(pixels[group[0]:group[-1]+2]).astype(np.int32)
                cv2.polylines(overlay,[curve],False,color,2,cv2.LINE_AA)
                on_image = ((curve[:,0]>=0)&(curve[:,0]<width)&(curve[:,1]>=0)&(curve[:,1]<height))
                anchors.extend(curve[on_image].tolist())
        if anchors:
            visible_boxes += 1
            x, y = min(anchors, key=lambda p: p[1])
            label = f"{box.label[:36]} [{box.category}]".encode("ascii", "replace").decode()
            cv2.putText(overlay, label, (min(x,max(0,width-180)), max(18,y-5)),
                        cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
    radius, cx, cy = fish.image_geometry(calibration, width, height)
    yy, xx = np.ogrid[:height,:width]
    inside = (xx-cx)**2 + (yy-cy)**2 <= radius**2
    image[inside] = overlay[inside]
    return visible_boxes


class BBoxOverlay:
    """Main-thread buffers; callers supply receive monotonic times explicitly.

    dynamicinfo has no acquisition stamp: bbox association is receive-time
    approximate. Ego pose prefers Header interpolation; auto mode explicitly
    falls back to receive-time interpolation for incompatible sensor clocks.
    """
    def __init__(self, args, sensors):
        self.max_age = args.bbox_max_age
        self.pose_gap = args.bbox_pose_max_gap
        self.pose_time_mode = getattr(args, "bbox_pose_time_mode", "auto")
        self.odom_time_offset = getattr(args, "bbox_odom_time_offset", 0.0)
        if not math.isfinite(self.odom_time_offset):
            raise ValueError("--bbox-odom-time-offset must be finite")
        if not all(math.isfinite(x) and x > 0 for x in (self.max_age,self.pose_gap)):
            raise ValueError("bbox age and pose gap must be finite and positive")
        self.key = common.zenoh_key(args.bbox_key)
        name, odom = common.select_optional_sensor(sensors, args.bbox_odom_name, common.ODOM_TYPES, "odometry")
        if odom is None:
            raise ValueError("world bbox overlay needs an odometry sensor in --sensor-config; use --no-bbox to disable")
        self.odom_sensor = odom
        self.odom_key = args.bbox_odom_key or common.zenoh_key(odom["topic"])
        self.base_from_odom = common.sensor_pose_in_ros_attach(odom)
        self.frames = deque(maxlen=32)
        self.poses = deque(maxlen=256)
        self.received_poses = deque(maxlen=256)
        self.last_odom_receive = -math.inf
        self.error = None
        self.pose_status = ""
        self.last_timing_warning = -math.inf

    def receive(self, key, payload, received):
        if key == self.key:
            try:
                boxes, invalid = decode_boxes(payload)
                self.frames.append((received, boxes, invalid))
                self.error = None
            except (ValueError, TypeError, RecursionError) as error:
                self.frames.clear()
                self.error = f"invalid bbox: {error}"
        elif key == self.odom_key:
            try:
                pose = common.parse_odometry(payload, self.base_from_odom)
                pose = replace(pose, stamp=pose.stamp+self.odom_time_offset)
                # Explicit absolute comparison: relative tolerances collapse
                # separate frames when ROS stamps contain Unix epoch seconds.
                if self.poses and pose.stamp < self.poses[-1].stamp - 1:
                    self.poses.clear()
                    self.received_poses.clear()
                    self.frames.clear()
                ordered = [p for p in self.poses if abs(p.stamp-pose.stamp) > 1e-9]
                ordered.append(pose)
                ordered.sort(key=lambda p:p.stamp)
                self.poses.clear()
                self.poses.extend(ordered[-256:])
                self.received_poses.append((received, pose))
                self.last_odom_receive = received
            except (ValueError, common.struct.error):
                self.poses.clear()
                self.received_poses.clear()

    def ego_pose(self, camera_stamp, camera_received, now):
        """Resolve a full world-from-base pose without silently mixing clocks."""
        nearest = (min(self.received_poses, key=lambda item:abs(item[0]-camera_received))
                   if self.received_poses else None)
        header_delta = camera_stamp-nearest[1].stamp if nearest else None
        mode = "header"
        if self.pose_time_mode != "receive":
            try:
                pose, _ = common.robot_pose_at(self.poses, deque(), camera_stamp, self.pose_gap)
            except ValueError:
                # A normal dropped/delayed odom packet must not activate this
                # fallback. Require fresh arrivals and an unmistakable offset.
                if (self.pose_time_mode == "header" or nearest is None
                        or abs(header_delta) <= max(.5,3*self.pose_gap)):
                    raise
                mode = "receive"
        else:
            mode = "receive"
        if mode == "receive":
            if nearest is None or abs(nearest[0]-camera_received) > self.pose_gap:
                raise ValueError("no odometry near camera receive time")
            # Retimestamp copies only. Keep original Header times for diagnostics.
            received_history = deque((replace(p,stamp=received) for received,p in self.received_poses), maxlen=256)
            pose, _ = common.robot_pose_at(received_history,deque(),camera_received,self.pose_gap)
            if now-self.last_timing_warning >= 5:
                print(f"[WARN] bbox ego pose uses RECEIVE time (approximate): camera-odom Header={header_delta:+.3f}s; "
                      "use --bbox-pose-time-mode header after fixing the publishers' clock")
                self.last_timing_warning = now
        xyz = pose[:3,3]
        yaw = math.degrees(math.atan2(pose[1,0],pose[0,0]))
        self.pose_status = (f"ego[{mode}] xyz=({xyz[0]:.2f},{xyz[1]:.2f},{xyz[2]:.2f})m yaw={yaw:.1f}deg"
                            + (f" dHeader={header_delta:+.3f}s" if header_delta is not None else ""))
        return pose

    def render(self, image, calibration, camera_stamp, camera_received, now):
        self.pose_status = ""
        if not self.frames:
            return self.error or "bbox: waiting for dynamicinfo"
        received, boxes, invalid = min(self.frames, key=lambda f:abs(f[0]-camera_received))
        if now-received > self.max_age or abs(received-camera_received) > self.max_age:
            return "bbox: stale / no nearby receive-time frame"
        if not boxes:
            return f"bbox: 0, invalid={invalid} (receive-time approximate)"
        if now-self.last_odom_receive > self.max_age:
            return "bbox: waiting for fresh world odometry"
        try:
            pose = self.ego_pose(camera_stamp,camera_received,now)
        except ValueError as error:
            return f"bbox: no matching ego pose ({error})"
        transform = optical_from_world(calibration, pose)
        count = draw_boxes(image, boxes, calibration, transform)
        return f"bbox: {count}/{len(boxes)}, invalid={invalid} (receive-time approximate)"
