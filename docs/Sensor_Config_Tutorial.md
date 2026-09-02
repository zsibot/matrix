# MATRiX Sensor Configuration Tutorial

[Project README](../README.md) · [中文传感器与通信指南](Sensor_and_Communication_CN.md)

This guide is aligned with the current `UMujocoConfigLibrary` implementation and the sensor templates under `Content/model/config/sensors`.

## 1. Configuration files

The source project uses:

~~~text
Content/model/config/config.json
Content/model/config/sensors/
├── config_default.json
├── config_fisheyecamera.json
├── config_infrared.json
├── config_lidar.json
├── config_panorama.json
└── config_zg.json
~~~

Packaged builds commonly expose the same tree under `Windows/UeSim/Content/model/` or `Linux/UeSim/Content/model/`.

`config.json` is the active robot configuration. Files in `sensors/` are templates. Editing a template does not change `config.json` until the launcher or a config-library operation applies it.

## 2. Current robot-level schema

~~~json
{
  "robot": {
    "robot_type": "xgb",
    "mujoco_model": "Content/model/xgb/xgb.xml",
    "main_body": "base_link",
    "weapon": "",
    "network_mode": "standalone",
    "sensor_sync_mode": false,
    "inside_mc": true,
    "hardware_simulation": false,
    "zenoh_router": "tcp/0.0.0.0:7447",
    "position": { "x": 0, "y": 0, "z": 1 },
    "state_port": "mujoco/state",
    "cmd_port": "mujoco/cmd",
    "mujoco_running": false,
    "sensors": {}
  }
}
~~~

Important corrections from older configurations:

- `state_port` and `cmd_port` are string Zenoh keys, not numeric UDP ports.
- Use only `standalone`, `server`, or `client` for `network_mode`.
- `sensor_sync_mode` is the only project-JSON synchronization switch.
- Do not use `synchronous_mode`, `synchronous_frequency`, `EgoView`, or per-sensor `synchronized`.
- `sensor_master_rate_hz`, `sensor_overrun_policy`, and `require_realtime_sensor_frequency` are legacy runtime pins and are removed when the current config library saves JSON.

The `mujoco_model` path must exist on the target machine. Do not copy a developer-specific absolute path into a distributed package.

## 3. Dynamic sensor objects

Every child of `robot.sensors` is one sensor instance. The object key is the instance name and must be unique:

~~~json
"sensors": {
  "camera": {
    "sensor_type": "rgb",
    "topic": "/front_camera/image/compressed"
  },
  "camera_1": {
    "sensor_type": "rgb",
    "topic": "/rear_camera/image/compressed"
  }
}
~~~

The sensor list is not limited to `camera`, `depth_sensor`, and `lidar`. Multiple sensors of the same type are valid when their names and topics are unique.

## 4. Supported sensor types

| `sensor_type` | Sensor | Typical template rate | Output |
|---|---|---:|---|
| `imu` | IMU | 500 Hz | ROS 2 IMU CDR |
| `odom` | Odometry | 100 Hz | ROS 2 Odometry CDR |
| `gps` | GPS | 100 Hz | Position/navigation data |
| `rgb` | Perspective RGB camera | 10 Hz | CompressedImage |
| `infrared` | Infrared/thermal camera | 10 Hz | CompressedImage |
| `depth` | Perspective depth camera | 10 Hz | Lossless depth PNG; optional raw float32 depth |
| `fisheye` | 181–360 degree fisheye camera | 10 Hz | CompressedImage |
| `panoramargb` | 360×180 equirectangular RGB | 10 Hz | CompressedImage |
| `mid360` | Livox Mid360 simulation | 10 Hz | PointCloud2 |
| `airy` | Airy/RoboSense simulation | 10 Hz | PointCloud2 |

A configurable generic LiDAR actor is also available in the runtime plugin.

Legacy `wargb` and `wadepth` types were replaced by `fisheye`. The current template set does not define `panoramadepth`.

## 5. Common fields

| Field | Meaning |
|---|---|
| `sensor_type` | Runtime sensor implementation |
| `topic` | ROS-style topic; the Zenoh bridge convention is `rt/<topic without leading slash>` |
| `frequency` | Target sampling/publish rate in Hz |
| `position` | Mount position in metres relative to `sensor_attach` |
| `rotation` | Roll, pitch, and yaw in degrees |
| `sensor_attach` | MuJoCo body name, usually `base_link` |
| `width` / `height` | Image dimensions |
| `fov` | Horizontal field of view |
| `frame_id` / `child_frame_id` | ROS 2 frame identifiers |
| `CubeFaceSize` | Panorama/fisheye cube capture resolution |
| `K1`–`K4` | Kannala–Brandt fisheye coefficients |
| `cloudmode` | Depth compatibility option |
| `draw_points` / `random_scan` | LiDAR display/scan options |
| `simulate_motion_distortion` | Airy motion-distortion time model |

Local sensor axes are `+X forward`, `+Y right`, and `+Z up`. Positions are metres.

## 6. Camera examples

### RGB

~~~json
"camera": {
  "sensor_type": "rgb",
  "topic": "/front_camera/image/compressed",
  "frequency": 10,
  "position": { "x": 0.18, "y": 0, "z": 0.3 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "height": 1080,
  "width": 1920,
  "fov": 120,
  "sensor_attach": "base_link"
}
~~~

### Depth

~~~json
"depth_sensor": {
  "sensor_type": "depth",
  "topic": "/front_depth/image/compressed",
  "frequency": 10,
  "position": { "x": 0.18, "y": 0, "z": 0.3 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "height": 480,
  "width": 640,
  "fov": 120,
  "cloudmode": false,
  "sensor_attach": "base_link"
}
~~~

The lossless PNG encoding stores metres as:

~~~text
depth_m = R + G / 255.0
~~~

Zero pixels are invalid/out-of-range. The standalone camera actor can additionally publish an `MDEP` float32 raw-depth payload.

### Fisheye

~~~json
"fisheye": {
  "sensor_type": "fisheye",
  "topic": "/fisheye/front_left/compressed",
  "frequency": 10,
  "position": { "x": 0.27, "y": 0, "z": 0.5 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "height": 1080,
  "width": 1920,
  "fov": 210,
  "CubeFaceSize": 512,
  "K1": 0,
  "K2": 0,
  "K3": 0,
  "K4": 0,
  "sensor_attach": "base_link"
}
~~~

### Panorama RGB

~~~json
"panoramargb": {
  "sensor_type": "panoramargb",
  "topic": "/panoramargb/front_camera/compressed",
  "frequency": 10,
  "position": { "x": 0, "y": 0, "z": 0.3 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "height": 1080,
  "width": 1920,
  "CubeFaceSize": 512,
  "sensor_attach": "base_link"
}
~~~

## 7. LiDAR examples

~~~json
"lidar": {
  "sensor_type": "mid360",
  "topic": "/front_lidar",
  "frequency": 10,
  "position": { "x": 0.2, "y": 0, "z": 0.1 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "draw_points": false,
  "random_scan": false,
  "sensor_attach": "base_link"
}
~~~

Use `airy` for the Airy/RoboSense template. `simulate_motion_distortion` controls whether Airy uses one pose for the full scan or per-ray motion poses and time offsets.

Mid360 and Airy simulate a complete template scan for each accepted frame. Under overload they drop expired scans rather than issuing multiple catch-up scans in one game frame.

## 8. Synchronization and timestamps

All camera, LiDAR, IMU, GPS, odometry, and robot-state headers use the shared `FRobotClock`.

Enable synchronized mode only at robot level:

~~~json
"sensor_sync_mode": true
~~~

Do not add `synchronized` to individual sensor objects.

Typical global boundaries are:

- IMU and robot-state: 500 Hz / 2 ms.
- GPS and odometry: 100 Hz / 10 ms.
- Camera and LiDAR: 10 Hz / 100 ms.

Asynchronous scheduling uses absolute deadlines. If the producer cannot maintain its target, it records the actual acquisition time and re-anchors instead of inventing timestamps or sending a burst of expired samples.

The configured rate is a target. Rendering, GPU readback, image encoding, raycasts, queues, Zenoh, the operating system, and network transport can all affect delivery time.

## 9. Zenoh keys

The bridge convention for ROS 2-compatible data is:

~~~text
JSON topic: /front_lidar
Zenoh key:  rt/front_lidar
~~~

Robot control uses fixed process-global keys:

~~~text
mujoco/state
mujoco/cmd
~~~

`tcp/0.0.0.0:7447` is a listen address. Local clients should connect to `tcp/127.0.0.1:7447`; remote clients should connect to `tcp/<host-ip>:7447`.

## 10. Recommended editing workflow

1. Back up the active `config.json`.
2. Load a current template from `Content/model/config/sensors`.
3. Add or remove sensor objects, keeping names and topics unique.
4. Validate JSON syntax.
5. Ensure `mujoco_model` and `sensor_attach` resolve on the target robot.
6. Apply the configuration through the launcher or restart the robot Spawn flow.
7. Monitor `rt/**` and `mujoco/**` with the tools shipped in the runtime package, if present.
8. Confirm header cadence separately from network arrival cadence.

## 11. Troubleshooting

- **No output:** verify the active `config.json`, sensor `topic`, unique object name, valid `sensor_attach`, and Zenoh session.
- **Wrong camera/LiDAR pose:** sensor pose is body-relative; attaching directly to a generated visual mesh requires the MuJoCo body-to-geom compensation implemented by the Spawn flow.
- **Fisheye not created:** use `sensor_type: fisheye` and `config_fisheyecamera.json`, not legacy wide-angle types.
- **Panorama is slow:** reduce `width`, `height`, `CubeFaceSize`, or `frequency`.
- **10 Hz arrival jitter:** compare message Header timestamps first. Network arrival time includes encoding, queues, Zenoh, scheduling, and network jitter.
- **Synchronized sensors disagree:** use one robot-level `sensor_sync_mode` and remove per-sensor synchronization fields.
- **Config save removes fields:** fields that are not part of the current schema may be intentionally removed; unknown sensor parameters are preserved through `RawJson`/template parameters.
