<div align="center">

<p><strong>English</strong> | <a href="docs/README_CN.md">简体中文</a></p>

# MATRiX v1.0.13

**A high-fidelity robot simulation platform powered by Unreal Engine, MuJoCo, and Zenoh**

<img src="demo_gif/Forest.png" alt="MATRiX high-fidelity simulation environment" width="800"/>

[Download](https://github.com/zsibot/matrix/releases/tag/v1.0.13) · [Quick Start](#quick-start) · [Documentation](#documentation) · [Robots & Maps](docs/Robots_and_Maps.md) · [Contributing](CONTRIBUTING.md)

</div>

MATRiX combines Unreal Engine 5 visualization, MuJoCo physics, configurable robot sensors, Zenoh transport, built-in motion control, and downloadable map DLCs. The v1.0.13 open release is a ready-to-run Linux x86_64 package; the core simulator does not require ROS 2.

## Highlights

- Runtime MJCF/XML loading and MuJoCo robot physics.
- RGB, infrared, depth, fisheye, panorama, LiDAR, IMU, odometry, and GPS sensors.
- Built-in motion control enabled by default; no separate controller process is required.
- Dynamic map catalog updates and automatic DLC downloads from the map-selection UI.
- Zenoh sensor transport and optional ROS 2 bridging.
- LiDAR-to-camera projection, Zenoh monitoring, sensor viewing, bounding-box, gimbal, and UDP test tools.
- Joint targets and actuator commands constrained by the current MuJoCo model limits.

## Requirements

The v1.0.13 simulator requires Linux x86_64 and a correctly installed graphics driver. It is not limited to Ubuntu 22.04. At least 16 GB of memory is recommended.

Ubuntu 22.04 x86_64 is required only when using the separately downloaded external motion controller; it is not a simulator requirement.

## Quick Start

Download all three archive parts plus `SHA256SUMS` from the [v1.0.13 Release](https://github.com/zsibot/matrix/releases/tag/v1.0.13). Keep the original filenames in one directory.

```bash
sha256sum -c SHA256SUMS
cat MATRiX_v1.0.13.tar.gz.part-* | tar -xzf -
cd MATRiX_v1.0.13
./UeSim.sh
```

The archive preserves executable permissions; no `chmod` step is required for `UeSim.sh` or the UeSim binary.

The release defaults to:

```text
mujoco_model:     model/xgb/xgb.xml
inside_mc:        true
sensor_sync_mode: false
zenoh_router:     tcp/0.0.0.0:7447
```

On the map-selection screen, select **UPDATE LIST** first, then select **DOWNLOAD** below a map to download its DLC automatically. If automatic download is unavailable, use the [Baidu Netdisk mirror (code: `6sth`)](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F) and follow the [manual DLC guide](docs/Map_DLC.md).

## Motion Control

Built-in control is the default (`robot.inside_mc=true`) and runs inside UeSim. The standalone `robot_mc` runtime is intentionally not included in the open package.

Users who need a separate controller process can download a supported runtime from [MATRiX_Robot_MC](https://github.com/GENISOM-AI/MATRiX_Robot_MC/releases), set `inside_mc=false` manually, start UeSim first, and then start that controller. Never run built-in and external motion control together. See the [motion-control guide](docs/Motion_Control.md).

## LiDAR-to-Camera Projection

The release includes `Tools/visualize_lidar_camera_projection.py`. Enable synchronized scheduling in `UeSim/Content/model/config/config.json` before use:

```json
"sensor_sync_mode": true
```

```bash
python3 -m pip install numpy opencv-python eclipse-zenoh
python3 Tools/visualize_lidar_camera_projection.py --check-only
python3 Tools/visualize_lidar_camera_projection.py
```

See the [projection guide](docs/Lidar_Camera_Projection.md) for calibration, coordinates, topic overrides, and troubleshooting.

## Documentation

| Topic | English | 中文 |
|---|---|---|
| Installation and startup | [Getting Started](docs/Getting_Started.md) | [快速开始](docs/Getting_Started_CN.md) |
| Release download and checksums | [Download Guide](docs/Release_Download.md) | [下载与校验](docs/Release_Download_CN.md) |
| Motion control | [Motion Control](docs/Motion_Control.md) | [运动控制](docs/Motion_Control_CN.md) |
| Maps and DLCs | [Map DLC](docs/Map_DLC.md) | [地图与 DLC](docs/Map_DLC_CN.md) |
| Robots and maps | [Robots and Maps](docs/Robots_and_Maps.md) | [机器人与地图](docs/Robots_and_Maps_CN.md) |
| LiDAR-camera projection | [Projection](docs/Lidar_Camera_Projection.md) | [投影与坐标系](docs/Lidar_Camera_Projection_CN.md) |
| Sensors and Zenoh | [Sensor Configuration](docs/Sensor_Config_Tutorial.md) | [传感器与通信](docs/Sensor_and_Communication_CN.md) |
| Python tools | — | [Python 工具](docs/Python_Tools_CN.md) |
| Controllers | [Controller Guide](docs/Controller_Guide.md) | [手柄与相机](docs/Controller_Guide_CN.md) |
| Gimbal UDP control | — | [Protocol](docs/Camera_Gimbal_UDP_JSON_Protocol_CN.md) · [UI tool](docs/Camera_Gimbal_UI_Tool_CN.md) |
| Zenoh 2D bounding boxes | — | [BBox tool](docs/Zenoh_BBox2D_CN.md) |
| RoamerX Lite integration | [Integration Guide](docs/RoamerX_Lite_Integration.md) | — |
| Pixel Streaming | [Pixel Streaming 2](docs/pixelstreaming_tutorial.md) | — |
| Advanced configuration | — | [高级配置](docs/Advanced_Configuration_CN.md) |
| Docker status | [Docker Support Status](docs/Docker_Tutorial.md) | — |
| Architecture and releases | [Maintainer Guide](docs/MAINTAINER_GUIDE.md) | — |
| Troubleshooting | — | [常见问题](docs/FAQ_CN.md) |
| Release changes | — | [v1.0.13 发布说明](docs/Release_Notes_CN.md) |

## Community

<div align="center">
  <img src="demo_gif/wechat.png" alt="GENISOM AI WeChat assistant QR code" style="height: 320px; width: auto; margin: 0 12px;"/>
  <p><em>Scan to add XinQi Robo; mention MATRiX to join the simulation community.</em></p>
</div>

## Contributing and Security

Bug reports and documentation improvements are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Report security issues privately as described in [SECURITY.md](SECURITY.md).

## Acknowledgements

- [MuJoCo-Unreal-Engine-Plugin](https://github.com/oneclicklabs/MuJoCo-Unreal-Engine-Plugin)
- [MuJoCo](https://github.com/google-deepmind/mujoco)
- [Unreal Engine](https://github.com/EpicGames/UnrealEngine)
- [CARLA](https://carla.org/)
