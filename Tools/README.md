# MATRiX v1.1.2 Python tools / Python 工具

[中文使用教程](../docs/Getting_Started_CN.md) | [English usage](../docs/Getting_Started.md)

本仓库保存工具源码；模型、Engine 和 UeSim 可执行文件通过 Release 下载。将整个 `Tools/` 放在解压的运行包中，并从发布包根目录运行命令。仿真器本身不需要这些 Python 依赖。使用 Python 3.10+；图形工具需要桌面显示环境。
Run commands from the release root. Python dependencies are optional for the simulator itself. Use Python 3.10+ and a desktop display for graphical tools.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r Tools/requirements.txt
```

`requirements.txt` 给出依赖范围，并非锁定的跨平台环境。Tkinter 通过系统包提供，Ubuntu/Debian 可按需安装 `python3-tk` 和 `python3-venv`。OpenCV 窗口需要 `opencv-python`，不使用 headless 版。
The requirements file gives dependency ranges, not a platform lockfile. Tkinter comes from the system package manager (`python3-tk` on Ubuntu/Debian). OpenCV windows require the desktop build.

| Entry / 入口 | Purpose / 用途 | Dependencies / 依赖 |
|---|---|---|
| `matrix_mc_udp_test.py` | 内置运控 / embedded-controller UDP commands | Python standard library |
| `send_spawn_udp.py` | 生成对象 / UDP spawn example, default `127.0.0.1:8081` | Standard library |
| `send_udp_voice.py` | 语音音频 UDP / voice audio sender | Standard library |
| `gimbal_udp_client.py` | 云台协议 / gimbal protocol CLI | Standard library |
| `gimbal_udp_ui.py` | 云台窗口 / gimbal UI | Tkinter + `gimbal_udp_client.py` |
| `zenoh_topic_monitor.py` | 主题、频率 / topic monitor | eclipse-zenoh |
| `zenoh_sensor_receiver.py` | 图像、深度、点云 / image, depth, point-cloud receiver | eclipse-zenoh, NumPy, OpenCV |
| `visualize_lidar_camera_projection.py` | 透视相机点云投影 / perspective projection | eclipse-zenoh, NumPy, OpenCV |
| `visualize_lidar_fisheye_projection.py` | 四路鱼眼与点云 / fisheye surround projection | Same, plus local projection helpers |
| `visualize_zenoh_bbox.py` | 分类、速度、详情 / categorized XY bbox view | eclipse-zenoh, Matplotlib, `bbox_motion.py` |
| `visualize_zenoh_bbox_2d.py` | 兼容固定范围 XY 视图 / legacy fixed-range XY view | eclipse-zenoh, Matplotlib |
| `zenoh_bbox_lidar_recorder.py` | 原始消息录制回放 / raw recording and replay | eclipse-zenoh, Tkinter, Pillow for images, local recording helpers |

`bbox_motion.py`、`fisheye_bbox_overlay.py`、`fisheye_surround_viewer.py`、`zenoh_recording.py` 是辅助模块，不是独立命令行入口。复制工具时保留整个 `Tools/` 目录；鱼眼入口还依赖 `visualize_lidar_camera_projection.py`。
The four helper modules are not CLI entry points. Keep the Tools directory together when copying it.

## Start / 启动

初始 `robot.sensors` 为空，不会自动发布传感器数据；`sensor_sync_mode=true`。请在传感器设置中加载并应用 `config_default.json`（IMU、Odom、GPS、RGB、Depth、Airy）或其他方案，再进入仿真并创建机器人。
The initial `robot.sensors` dictionary is empty, so sensors do not publish automatically. `sensor_sync_mode=true` is retained. Load and apply `config_default.json` (IMU, odometry, GPS, RGB, depth, Airy), or another scheme, before entering the simulation and spawning the robot.

```bash
python3 Tools/zenoh_topic_monitor.py --key '**'
python3 Tools/zenoh_sensor_receiver.py --key 'rt/**'
python3 Tools/visualize_zenoh_bbox.py
python3 Tools/zenoh_bbox_lidar_recorder.py
```

离线检查无需启动 UeSim / Offline calibration checks:

```bash
python3 Tools/visualize_lidar_camera_projection.py \
  --sensor-config UeSim/Content/model/config/sensors/config_default.json --check-only
python3 Tools/visualize_lidar_fisheye_projection.py --check-only
```

`--check-only` 只读取配置，不代表传感器已启用或有实时数据。远端连接通过各工具的 `--connect` 或 UDP 工具的 `--host` 设置；参数以 `--help` 为准。
Offline checks do not verify live data. Use `--connect` for Zenoh tools and `--host` for UDP tools; see each entry's `--help`.

## Guides / 详细说明

- [Perspective projection](../docs/Lidar_Camera_Projection.md) / [透视投影](../docs/Lidar_Camera_Projection_CN.md)
- [四路鱼眼投影与包围盒叠加](../docs/Lidar_Fisheye_Projection_CN.md)
- [录制、离线预览与回放](../docs/Zenoh_Recording_CN.md)
- [固定范围包围盒视图](../docs/Zenoh_BBox2D_CN.md)
- [云台控制](../docs/Camera_Gimbal_UI_Tool_CN.md)

接收器支持 `--stream-type semantic`，可查看本次随包语义相机的原始类别 ID PNG；配色预览不修改原始类别数据。
The receiver accepts the bundled semantic camera’s lossless class-ID PNGs via `--stream-type semantic`; display colors do not modify the raw labels.

[语义相机配置与显示](../docs/Semantic_Camera_CN.md)
