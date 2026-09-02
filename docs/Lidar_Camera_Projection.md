# MATRiX LiDAR-to-camera projection

[Back to README](../README.md) | [中文](Lidar_Camera_Projection_CN.md)

`Tools/visualize_lidar_camera_projection.py` subscribes to a rigidly mounted camera and LiDAR over Zenoh, pairs their ROS Header timestamps, and projects the point cloud onto the RGB image using a fixed camera-from-LiDAR extrinsic. It does not use IMU, odometry, SLAM, or motion compensation.

## Prerequisites

Install the Python dependencies:

```bash
python3 -m pip install numpy opencv-python eclipse-zenoh
```

In `UeSim/Content/model/config/config.json`, enable synchronized sensor scheduling:

```json
"sensor_sync_mode": true
```

The selected camera and LiDAR should use the same `frequency` and `sensor_attach`. Their `position` and `rotation` fields define the fixed extrinsic when no calibration file is supplied.

## Run

Start MATRiX, then run from the release root:

```bash
# Validate sensor selection, intrinsics, and extrinsics without opening Zenoh.
python3 Tools/visualize_lidar_camera_projection.py --check-only

# Open the live overlay.
python3 Tools/visualize_lidar_camera_projection.py
```

The release layout is detected automatically. Defaults are:

```text
sensor config: UeSim/Content/model/config/config.json
Zenoh router:  tcp/127.0.0.1:7447
pairing:       exact camera/LiDAR Header nanoseconds
```

Press `S` to save the current overlay under `Saved/LidarCameraProjection/`. Press `Q` or `Esc` to exit.

## Common options

```bash
# Select named sensors when the configuration contains more than one.
python3 Tools/visualize_lidar_camera_projection.py \
  --camera-name camera --lidar-name lidar

# Override Zenoh keys.
python3 Tools/visualize_lidar_camera_projection.py \
  --camera-key rt/front_camera/image/compressed \
  --lidar-key rt/front_lidar

# Connect to a remote simulator.
python3 Tools/visualize_lidar_camera_projection.py \
  --connect tcp/192.168.1.100:7447

# Permit a nearest pair within 5 ms for legacy data only.
python3 Tools/visualize_lidar_camera_projection.py --max-time-diff 0.005
```

Exact pairing (`--max-time-diff 0`, the default) should be used to validate current synchronized data.

## Calibration JSON

For a calibrated physical pair, pass a JSON file containing `T_camera_optical_lidar`, camera intrinsics, image size, and optional Brown–Conrady distortion coefficients:

```bash
python3 Tools/visualize_lidar_camera_projection.py \
  --calibration-json calibration/lidar_camera.json
```

The transform maps LiDAR FLU points in metres into the camera optical frame. If calibration software provides the inverse direction, invert it before use.

## Troubleshooting

- Both packet counts stay at zero: verify UeSim, the Zenoh endpoint, and TCP port 7447.
- Only one stream arrives: verify `--camera-key`, `--lidar-key`, and the active sensor topics.
- Both arrive but never pair: verify `sensor_sync_mode`, matching frequencies, and the displayed Header delta.
- Image appears without projected points: verify sensor selection, shared mounting frame, transform direction, image intrinsics, and that point-cloud coordinates are already ROS FLU in metres.
- Projection is correct while stationary but wrong in motion: investigate timestamps and queued old frames; a rigid mounting does not require a changing extrinsic.
