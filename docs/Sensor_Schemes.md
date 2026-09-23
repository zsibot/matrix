# MATRiX v1.1.2 sensor configuration

[Usage](Getting_Started.md) | [中文](Sensor_Schemes_CN.md)

## Activate a scheme

The active file is `UeSim/Content/model/config/config.json`. The initial `robot.sensors` dictionary is empty, so sensors do not publish automatically. `sensor_sync_mode=true` is retained. Load and apply `config_default.json` (IMU, odometry, GPS, RGB, depth, Airy), or another scheme, before entering the simulation and spawning the robot. Preset files do not become active merely by existing on disk.

Load a scheme from `UeSim/Content/model/config/sensors/` in the robot/sensor settings UI, check mounting frames, rates and topics, and apply it before entering the simulation. Verify the saved `robot.sensors` and received topics. For manual edits, close UeSim and copy only the scheme's sensor dictionary into `robot.sensors`; do not replace the entire main configuration.

Start with `config_default.json`. A tool's `--sensor-config` argument only selects its input file; it does not activate sensors in UeSim.

## Included schemes

| File | Sensors |
|---|---|
| `config_default.json` | IMU, odometry, GPS, RGB, depth, Airy |
| `config_data.json` | Front LiDAR IMU, odometry, GPS, calibrated RGB, MID360 |
| `mid360_slam.json` | MID360, odometry, IMU |
| `config_lidar.json` | MID360 and Airy |
| `config_dual_airy_gpu.json` | Two GPU Airy sensors with motion distortion |
| `config_surround4_airy_calibration_approx.json` | Four fisheyes, two Airy sensors, IMU, odometry; approximate calibration |
| `config_zg.json` | RGB and Airy |
| `config_v1.0.12_zgwt.json` | Three IMUs, odometry, GPS, front/rear cameras and Airy; historical filename retained |
| `config_all_sensors.json` | Eleven sensor types; higher rendering and network load |
| `config_fisheyecamera.json` | Fisheye |
| `config_panorama.json` | Panoramic RGB |
| `config_ptzrgb.json` | Gimbal RGB |
| `config_infrared.json` | Infrared |
| `config_semantic.json` | Perspective semantic camera, class-ID PNG |
| `config_rgb_semantic.json` | Matched RGB/semantic pose, intrinsics and rate |
| `empty.json` | Empty scheme |

This rebuild includes `config_semantic.json` and `config_rgb_semantic.json` for semantic-only and aligned RGB/semantic capture. Semantic output is a lossless class-ID PNG that the receiver can colorize. Semantic cameras are optional schemes; no sensors are active initially.

## Parameters and GPU LiDAR

Position is in metres, rotation in degrees, and `frequency` in Hz. Check `enabled` and the model's `sensor_attach` frame. Perspective cameras accept `fx/fy/cx/cy` and Brown–Conrady `K1/K2/K3/P1/P2`; `fx/fy=0` and `cx/cy=-1` select FOV/image-center defaults.

Airy and MID360 share the `backend` field (`gpu` or `cpu`). Several included schemes request GPU acceleration, which needs a working NVIDIA CUDA/OptiX driver environment. The package includes `libAiryOptix.so` and `AiryOptix.ptx` under `UeSim/Plugins/RobotSensorSimulation/Binaries/Linux/`. Read the actual backend from startup logs. Initialization may fall back to CPU; runtime GPU errors stop the affected sensor. To select CPU explicitly, change each LiDAR's `backend` in the selected scheme to `cpu` and reapply it.

`simulate_motion_distortion` enables rolling-scan motion distortion. Stop the robot or disable it for initial geometry checks; equal Header timestamps do not deskew individual points. Airy measurement-error fields include `RangeBiasMeters`, `RangeNoiseStdDevMeters`, `ReturnDropoutProbability`, and `MeasurementRandomSeed`. Zero noise is a simulation setting, not a physical-device accuracy claim.

The shared image/point-cloud publisher uses Header `frame_id=map`, while LiDAR XYZ remains sensor-local ROS FLU. A bridge must not treat those points as world coordinates based on the label alone. Airy organized RoboSense point timestamps are absolute seconds; MID360 uses a separate per-point-time convention.

## Check the data

Install [tool dependencies](../Tools/README.md), activate a scheme, then run:

```bash
python3 Tools/zenoh_topic_monitor.py --key '**'
python3 Tools/zenoh_sensor_receiver.py --key 'rt/**'
# Offline calibration checks; no network connection or simulator launch
python3 Tools/visualize_lidar_camera_projection.py \
  --sensor-config UeSim/Content/model/config/sensors/config_default.json --check-only
python3 Tools/visualize_lidar_fisheye_projection.py --check-only
```

If no samples arrive, check that the robot and sensors exist in the scene, the active scheme is nonempty, and TCP 7447 is reachable. Scheme topics such as `/front_lidar` usually appear as `rt/front_lidar`; use the monitor to confirm actual keys. Measure performance on your target hardware and map, particularly for all-sensor and surround-view schemes.

[Semantic camera / 语义相机使用说明](Semantic_Camera.md)
