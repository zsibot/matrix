# MATRiX v1.0.13 Python 工具

[返回中文主页](README_CN.md) | [快速开始](Getting_Started_CN.md)

v1.0.13 Linux 运行包在根目录提供 `Tools/`。以下脚本与本次 Release 中的版本一致；完整参数始终以 `python3 Tools/<脚本>.py --help` 为准。

## 工具清单

| 脚本 | 用途 | 主要依赖 |
|---|---|---|
| `zenoh_topic_monitor.py` | 显示 Zenoh topic、频率、大小和延迟 | `eclipse-zenoh` |
| `zenoh_sensor_receiver.py` | 查看相机、深度和 LiDAR 数据 | `eclipse-zenoh`、`numpy`、`opencv-python` |
| `visualize_lidar_camera_projection.py` | 将 LiDAR 点云投影到 RGB 图像 | `eclipse-zenoh`、`numpy`、`opencv-python` |
| `visualize_zenoh_bbox.py` | 显示 3D 包围盒 | `eclipse-zenoh`、`matplotlib` |
| `visualize_zenoh_bbox_2d.py` | 显示固定范围的 2D 俯视包围盒 | `eclipse-zenoh`、`matplotlib` |
| `matrix_mc_udp_test.py` | 内置运控起身、行走、转向和动作测试 | Python 标准库 |
| `gimbal_udp_client.py` | 云台 UDP/JSON 命令行客户端 | Python 标准库 |
| `gimbal_udp_ui.py` | 云台四方向图形测试工具 | Python 标准库、Tkinter |
| `send_spawn_udp.py` | 发送场景对象生成 UDP JSON | Python 标准库 |
| `send_udp_voice.py` | 发送 JSON 或 MP3 UDP 数据 | Python 标准库 |

## 安装常用依赖

```bash
python3 -m pip install eclipse-zenoh numpy opencv-python matplotlib
```

图形工具需要桌面显示环境。SSH 无图形会话不能直接显示 OpenCV、Matplotlib 或 Tkinter 窗口。

## Zenoh topic 监控

UeSim 默认监听 `tcp/0.0.0.0:7447`，本机工具在 client 模式下默认连接 `tcp/127.0.0.1:7447`。

```bash
python3 Tools/zenoh_topic_monitor.py --key '**'
python3 Tools/zenoh_topic_monitor.py --key 'rt/**'
python3 Tools/zenoh_topic_monitor.py --connect tcp/192.168.1.100:7447
```

先订阅 `**` 发现实际 key，再按传感器配置缩小范围。界面切换传感器预设后，活动 topic 可能发生变化。

## 传感器接收

```bash
python3 Tools/zenoh_sensor_receiver.py --key 'rt/**'
python3 Tools/zenoh_sensor_receiver.py --key 'rt/front_lidar' --stream-type lidar
python3 Tools/zenoh_sensor_receiver.py \
  --connect tcp/192.168.1.100:7447 \
  --key 'rt/**'
```

接收器可自动识别压缩图像、深度图和 ROS 2 `PointCloud2`。使用 `--auto-range` 调整深度显示，使用 `--height-auto-range` 调整 LiDAR 高度图。

## LiDAR 到相机投影

使用前编辑 `UeSim/Content/model/config/config.json`：

```json
"sensor_sync_mode": true
```

然后从发布包根目录运行：

```bash
python3 Tools/visualize_lidar_camera_projection.py --check-only
python3 Tools/visualize_lidar_camera_projection.py
```

默认相机 key 为 `rt/front_camera/image/compressed`，LiDAR key 为 `rt/front_lidar`。按 `S` 保存，按 `Q` 或 `Esc` 退出。详细说明见 [LiDAR 到相机投影](Lidar_Camera_Projection_CN.md)。

## 包围盒查看

```bash
python3 Tools/visualize_zenoh_bbox.py --key rt/dynamicinfo
python3 Tools/visualize_zenoh_bbox_2d.py --key rt/dynamicinfo
```

2D 工具默认显示 X `-250…150 m`、Y `-50…50 m` 的 ROS FLU 世界坐标。详细消息格式见 [Zenoh 2D 包围盒工具](Zenoh_BBox2D_CN.md)。

## 内置运控 UDP 测试

```bash
python3 Tools/matrix_mc_udp_test.py stand
python3 Tools/matrix_mc_udp_test.py walk --stand-first --forward 0.25 --duration 3
python3 Tools/matrix_mc_udp_test.py rotate --yaw 0.25 --duration 2
python3 Tools/matrix_mc_udp_test.py passive
```

远程控制增加 `--host <仿真器IP>`。默认 UDP 端口为 7447，速度输入超过 0.5 秒未刷新会失效。

## 云台工具

```bash
python3 Tools/gimbal_udp_client.py --port 8870 --gimbal-id camera_gimbal ping
python3 Tools/gimbal_udp_ui.py \
  --port 8870 \
  --state-port 8871 \
  --npc-state-port 8872 \
  --gimbal-id camera_gimbal
```

UeSim 中的 PTZRGB 云台 UDP 服务必须先启动。协议和 UI 操作见 [云台 UDP/JSON 协议](Camera_Gimbal_UDP_JSON_Protocol_CN.md)及[图形测试工具](Camera_Gimbal_UI_Tool_CN.md)。

## 排查

- `ModuleNotFoundError`：使用运行脚本的同一个 Python 执行 `python3 -m pip install ...`。
- 无 Zenoh 数据：先监控 `**`，再检查 UeSim 日志、IP、TCP 7447、防火墙和活动传感器。
- 图形窗口无法打开：确认当前会话有桌面显示环境。
- 参数不识别：运行对应脚本的 `--help`，不要照搬旧版本参数。
