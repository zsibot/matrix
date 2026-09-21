"""Live single-camera / 2x2 fisheye point-cloud and world-bbox display."""
from collections import deque
from dataclasses import dataclass, field
import copy
import json
import signal
import threading
import time

import visualize_lidar_camera_projection as common
import visualize_lidar_fisheye_projection as fish


@dataclass
class View:
    name: str
    lidar_name: str
    calibration: fish.FisheyeCalibration
    camera_key: str
    lidar_key: str
    cameras: deque = field(default_factory=lambda: deque(maxlen=16))
    camera_receives: dict = field(default_factory=dict)
    clean: object = None
    panel: object = None
    last_update: float = 0
    last_stamp: int | None = None
    expired: bool = False


def load_views(args):
    with args.sensor_config.open(encoding="utf-8-sig") as stream:
        sensors = common.sensor_map(json.load(stream), args.sensor_config)
    names = [args.camera_name]
    if args.camera_name == "all":
        if args.calibration_json or args.camera_key:
            raise ValueError("--calibration-json / --camera-key require a single --camera-name")
        names = [name for name,s in sensors.items()
                 if s.get("sensor_type", "").lower() == "fisheye" and s.get("enabled", True)]
        order = ("surround_front", "surround_rear", "surround_left", "surround_right")
        names.sort(key=lambda n: order.index(n) if n in order else len(order))
        if not 1 <= len(names) <= 4:
            raise ValueError("--camera-name all requires 1 to 4 enabled fisheye cameras")
    views = []
    for name in names:
        selected = copy.copy(args)
        selected.camera_name = name
        if args.lidar_name == "auto":
            preferred = "rear_lidar" if name == "surround_rear" else "front_lidar"
            if preferred in sensors:
                selected.lidar_name = preferred
            else:
                selected.lidar_name = None  # only auto-select an unambiguous sensor
        calibration, camera_key, lidar_key = fish.load_calibration(selected)
        if calibration.synchronized is False:
            raise ValueError("sensor_sync_mode must be true")
        views.append(View(name, selected.lidar_name or lidar_key, calibration, camera_key, lidar_key))
    if len({v.camera_key for v in views}) != len(views):
        raise ValueError("each camera in the mosaic needs a distinct topic")
    return views, sensors


def title(image, text, line=0, color=(255,255,255)):
    cv2 = common.cv2
    position = (12, 25+line*23)
    cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX, .52, (0,0,0), 3, cv2.LINE_AA)
    cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX, .52, color, 1, cv2.LINE_AA)


def compose_panels(panels):
    """Aspect-preserving 2x2 tiling; this is not panorama stitching."""
    np, cv2 = common.np, common.cv2
    if len(panels) == 1:
        return panels[0]
    height = max(p.shape[0] for p in panels)
    width = max(p.shape[1] for p in panels)
    canvas = np.zeros((height*2,width*2,3),np.uint8)
    for i,panel in enumerate(panels):
        scale = min(width/panel.shape[1],height/panel.shape[0])
        w,h = round(panel.shape[1]*scale),round(panel.shape[0]*scale)
        resized = cv2.resize(panel,(w,h),interpolation=cv2.INTER_AREA) if panel.shape[:2] != (h,w) else panel
        x,y = (i%2)*width+(width-w)//2,(i//2)*height+(height-h)//2
        canvas[y:y+h,x:x+w] = resized
    return canvas


def run(args):
    np, cv2 = common.np, common.cv2
    if np is None or cv2 is None:
        print("[ERROR] install numpy opencv-python eclipse-zenoh")
        return 2
    try:
        common.validate_args(args)
        views, sensors = load_views(args)
        bbox = None
        if not args.no_bbox:
            from fisheye_bbox_overlay import BBoxOverlay
            bbox = BBoxOverlay(args, sensors)
            for view in views:
                if sensors[view.name].get("sensor_attach") != bbox.odom_sensor.get("sensor_attach"):
                    raise ValueError("camera and odometry must share sensor_attach for world bbox projection")
        for view in views:
            cal = view.calibration
            print(f"[INFO] {view.name} <- {view.lidar_name}: {view.camera_key} / {view.lidar_key}")
            print(f"[INFO] FOV={cal.fov_deg:g} K={fish.intrinsics_for_image(cal,*cal.expected_image_size)} D={cal.distortion}")
            print(np.array2string(cal.transform_camera_optical_from_lidar,precision=6))
        if bbox:
            print(f"[INFO] bbox={bbox.key}; world odometry={bbox.odom_key}")
            print("[INFO] dynamicinfo has no Header: bbox receive-time matching is approximate; odometry must use the same ROS world as bbox")
        if args.check_only:
            return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(f"[ERROR] {error}")
        return 2
    if common.zenoh is None:
        print("[ERROR] install eclipse-zenoh")
        return 2

    keys = {v.camera_key for v in views} | {v.lidar_key for v in views}
    if bbox:
        keys.update((bbox.key,bbox.odom_key))
    # Per-topic bounded queues prevent high-rate odometry starving images.
    incoming = {key:deque(maxlen=256 if bbox and key==bbox.odom_key else 16) for key in keys}
    clouds = {v.lidar_key:deque(maxlen=16) for v in views}
    cloud_cache = {}
    lock = threading.Lock()
    stop = threading.Event()
    session, subscribers = None, []
    window = "UeSim Surround Fisheye | LiDAR + BBox"
    for view in views:
        width,height = view.calibration.expected_image_size
        view.panel = np.full((height,width,3),24,np.uint8)
        title(view.panel,view.name)
        title(view.panel,"Waiting for synchronized camera / LiDAR Headers...",1)

    def callback(key):
        def receive(sample):
            received = time.monotonic()
            payload = common.payload_bytes(sample.payload)
            with lock:
                incoming[key].append((received,payload))
        return receive

    previous_signals = {}
    try:
        session = common.zenoh.open(common.build_zenoh_config(args))
        for key in sorted(keys):
            subscribers.append(session.declare_subscriber(key,callback(key)))
        for sig in (signal.SIGINT,signal.SIGTERM):
            previous_signals[sig] = signal.signal(sig,lambda *_:stop.set())
        cv2.namedWindow(window,cv2.WINDOW_NORMAL)
        mosaic = compose_panels([v.panel for v in views])
        cv2.imshow(window,mosaic)
        if args.window_width:
            cv2.resizeWindow(window,args.window_width,round(args.window_width*mosaic.shape[0]/mosaic.shape[1]))
        started = time.monotonic()
        timeout_reported = False
        last_warning = {}
        print("[INFO] 2x2 order: front, rear / left, right. S saves full mosaic; Q/Esc exits.")
        while not stop.is_set():
            with lock:
                pending = {key:list(queue) for key,queue in incoming.items()}
                for queue in incoming.values():
                    queue.clear()
                # All panels render the same input snapshot. Processing earlier
                # panels must not age out bbox/odometry for the later panels.
                snapshot_time = time.monotonic()
            for key, packets in pending.items():
                for received,payload in packets:
                    try:
                        if bbox and key in (bbox.key,bbox.odom_key):
                            bbox.receive(key,payload,received)
                            continue
                        packet = common.RawFrame(common.message_stamp_ns(payload),payload)
                        if key in clouds:
                            if clouds[key] and packet.stamp_ns < clouds[key][-1].stamp_ns-1_000_000_000:
                                clouds[key].clear()
                                cloud_cache.clear()
                            clouds[key].append(packet)
                        for view in views:
                            if key == view.camera_key:
                                if view.last_stamp is not None and packet.stamp_ns < view.last_stamp-1_000_000_000:
                                    view.cameras.clear()
                                    view.last_stamp = None
                                view.cameras.append(packet)
                                view.camera_receives[packet.stamp_ns] = received
                                stamps = {p.stamp_ns for p in view.cameras}
                                view.camera_receives = {s:r for s,r in view.camera_receives.items() if s in stamps}
                    except (ValueError,common.struct.error) as error:
                        if received-last_warning.get(key,0) > 1:
                            print(f"[WARN] {key}: {error}")
                            last_warning[key] = received
            changed = False
            updated_views = []
            for view in views:
                pair = common.synchronized_pair(view.cameras,clouds[view.lidar_key],round(args.max_time_diff*1e9))
                if pair and (view.last_stamp is None or pair[0].stamp_ns > view.last_stamp):
                    camera_packet,lidar_packet = pair
                    try:
                        camera = common.parse_compressed_image(camera_packet.payload)
                        cache_key = (view.lidar_key,lidar_packet.stamp_ns)
                        if cache_key not in cloud_cache:
                            cloud_cache[cache_key] = common.parse_pointcloud2(lidar_packet.payload)
                        cloud = cloud_cache[cache_key]
                        image,stats,_ = fish.project_cloud(camera.image_bgr,cloud,view.calibration,
                            args.min_range,args.max_range,args.point_radius,args.alpha,args.max_points,args.color_mode)
                        if bbox:
                            status = bbox.render(image,view.calibration,camera.stamp,
                                                 view.camera_receives[camera_packet.stamp_ns],snapshot_time)
                            title(image,status,2,(100,220,255))
                            if bbox.pose_status:
                                title(image,bbox.pose_status,3,(100,220,255))
                        title(image,f"{view.name} / {view.lidar_name}")
                        delta_ms = (camera_packet.stamp_ns-lidar_packet.stamp_ns)/1e6
                        title(image,f"t={camera.stamp:.3f}s  dt={delta_ms:+.2f}ms  points={stats.visible_pixels}",1)
                        view.clean = camera.image_bgr
                        view.panel = image
                        updated_views.append(view)
                        view.expired = False
                        changed = True
                    except (ValueError,common.struct.error,cv2.error) as error:
                        print(f"[WARN] {view.name}: {error}")
                    view.last_stamp = camera_packet.stamp_ns
                    # Consume only this camera. A LiDAR packet may serve three
                    # simultaneous cameras and must remain in the shared buffer.
                    remaining = [p for p in view.cameras if p.stamp_ns>camera_packet.stamp_ns]
                    view.cameras.clear()
                    view.cameras.extend(remaining)
            # Presentation expiry is separate from input matching. Start its
            # timer for every updated panel together after the entire batch,
            # never expire a panel while constructing that same mosaic.
            presented_at = time.monotonic()
            for view in updated_views:
                view.last_update = presented_at
            expiry = min(args.overlay_timeout,args.bbox_max_age) if bbox else args.overlay_timeout
            for view in views:
                if view.clean is not None and not view.expired and snapshot_time-view.last_update > expiry:
                    view.panel = view.clean.copy()
                    title(view.panel,view.name)
                    title(view.panel,"Overlay expired - waiting for synchronized data",1)
                    view.expired = True
                    changed = True
            active_clouds = {(key,p.stamp_ns) for key,packets in clouds.items() for p in packets}
            cloud_cache = {key:value for key,value in cloud_cache.items() if key in active_clouds}
            if changed:
                mosaic = compose_panels([v.panel for v in views])
                cv2.imshow(window,mosaic)
            if not timeout_reported and time.monotonic()-started > args.timeout:
                missing = [v.name for v in views if v.clean is None]
                if missing:
                    print(f"[WARN] no synchronized pair for: {', '.join(missing)}; check topics and sensor_sync_mode")
                if len(missing)==len(views):
                    return 5
                timeout_reported = True
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'),ord('Q'),27):
                break
            if key in (ord('s'),ord('S')):
                args.save_dir.mkdir(parents=True,exist_ok=True)
                path = args.save_dir/time.strftime("fisheye_lidar_bbox_%Y%m%d_%H%M%S.png")
                print(f"[INFO] saved {path}" if cv2.imwrite(str(path),mosaic) else f"[WARN] could not save {path}")
            if cv2.getWindowProperty(window,cv2.WND_PROP_VISIBLE)<1:
                break
            if not any(pending.values()):
                time.sleep(.003)
        return 0
    except Exception as error:
        print(f"[ERROR] viewer: {error}")
        return 3
    finally:
        for subscriber in subscribers:
            try:
                subscriber.undeclare()
            except Exception:
                pass
        if session is not None:
            session.close()
        for sig,handler in previous_signals.items():
            signal.signal(sig,handler)
        cv2.destroyAllWindows()
