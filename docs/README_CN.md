<div align="center">

<p><a href="../README.md">English</a> | <strong>简体中文</strong></p>

# MATRiX v1.0.13

**基于 Unreal Engine、MuJoCo 与 Zenoh 的高保真机器人仿真平台**

<img src="../demo_gif/Forest.png" alt="MATRiX 高保真仿真环境" width="800"/>

[GitHub 下载](https://github.com/zsibot/matrix/releases/tag/v1.0.13) · [百度网盘](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q)（`118g`） · [快速开始](#快速开始) · [文档中心](#文档中心) · [机器人与地图](Robots_and_Maps_CN.md) · [参与贡献](../CONTRIBUTING.md)

</div>

MATRiX 将 Unreal Engine 5 可视化、MuJoCo 物理仿真、可配置机器人传感器、Zenoh 通信、内置运动控制和地图 DLC 下载整合在一起。v1.0.13 开源版本提供可直接运行的 Linux x86_64 包；仿真器本体不依赖 ROS 2。

## 核心能力

- 运行时加载 MJCF/XML，并执行 MuJoCo 机器人动力学仿真；
- RGB、红外、深度、鱼眼、全景、LiDAR、IMU、里程计和 GPS；
- 默认启用内置运控，无需额外控制器进程；
- 地图列表动态更新，并可从地图卡片自动下载 DLC；
- Zenoh 传感器通信和可选 ROS 2 bridge；
- LiDAR 到相机投影、Zenoh 监控、传感器查看、包围盒、云台和 UDP 测试工具；
- 按 MuJoCo 关节和执行器范围限制控制目标，优化关节限位安全性。

## 运行要求

v1.0.13 仿真器需要 Linux x86_64 环境和正确安装的显卡驱动，不限定 Ubuntu 22.04。建议至少 16 GB 内存。

只有另行下载的独立运控及其依赖安装环境限定为 Ubuntu 22.04 x86_64；该限制不适用于仿真器本体。

## 快速开始

可任选一种下载方式：

- GitHub：从 [v1.0.13 Release](https://github.com/zsibot/matrix/releases/tag/v1.0.13) 下载全部 3 个压缩分片和 `SHA256SUMS`，保持原文件名并放在同一目录；
- 百度网盘：从 [Linux 运行包分享](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q)下载完整包，提取码 `118g`。

使用 GitHub 分片时执行：

```bash
sha256sum -c SHA256SUMS
cat MATRiX_v1.0.13.tar.gz.part-* | tar -xzf -
cd MATRiX_v1.0.13
./UeSim.sh
```

压缩包已保留可执行权限，不需要对 `UeSim.sh` 或 UeSim 二进制执行 `chmod`。

发布默认配置：

```text
mujoco_model:     model/xgb/xgb.xml
inside_mc:        true
sensor_sync_mode: false
zenoh_router:     tcp/0.0.0.0:7447
```

进入地图选择界面后，先点击 **UPDATE LIST（更新列表）** 获取最新列表，再点击目标地图下方的 **DOWNLOAD（下载）** 自动下载 DLC。自动下载不可用时，可从[百度网盘（提取码：`6sth`）](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F)手动下载，详见[地图与 DLC](Map_DLC_CN.md)。

## 运动控制

默认 `robot.inside_mc=true`，内置运控随 UeSim 启动。开源包不包含独立 `robot_mc`、其依赖和安装脚本。

确需独立进程时，从 [MATRiX_Robot_MC Releases](https://github.com/GENISOM-AI/MATRiX_Robot_MC/releases) 下载受支持版本，手动设置 `inside_mc=false`，先启动 UeSim，再启动独立运控。两种控制器不能同时运行，详见[运动控制指南](Motion_Control_CN.md)。

## LiDAR 到相机投影

发布包提供 `Tools/visualize_lidar_camera_projection.py`。使用前在 `UeSim/Content/model/config/config.json` 中启用同步：

```json
"sensor_sync_mode": true
```

```bash
python3 -m pip install numpy opencv-python eclipse-zenoh
python3 Tools/visualize_lidar_camera_projection.py --check-only
python3 Tools/visualize_lidar_camera_projection.py
```

标定、坐标系、topic 覆盖和排查见 [LiDAR 到相机投影说明](Lidar_Camera_Projection_CN.md)。

## 文档中心

| 主题 | 中文 | English |
|---|---|---|
| 安装与启动 | [快速开始](Getting_Started_CN.md) | [Getting Started](Getting_Started.md) |
| Release 下载与校验 | [下载与校验](Release_Download_CN.md) | [Download Guide](Release_Download.md) |
| 运动控制 | [运动控制](Motion_Control_CN.md) | [Motion Control](Motion_Control.md) |
| 地图与 DLC | [地图与 DLC](Map_DLC_CN.md) | [Map DLC](Map_DLC.md) |
| 机器人与地图 | [机器人与地图](Robots_and_Maps_CN.md) | [Robots and Maps](Robots_and_Maps.md) |
| LiDAR 到相机投影 | [投影与坐标系](Lidar_Camera_Projection_CN.md) | [Projection](Lidar_Camera_Projection.md) |
| 传感器与 Zenoh | [传感器与通信](Sensor_and_Communication_CN.md) | [Sensor Configuration](Sensor_Config_Tutorial.md) |
| Python 工具 | [Python 工具](Python_Tools_CN.md) | — |
| 手柄与相机 | [手柄与相机](Controller_Guide_CN.md) | [Controller Guide](Controller_Guide.md) |
| 云台 UDP 控制 | [协议](Camera_Gimbal_UDP_JSON_Protocol_CN.md) · [UI 工具](Camera_Gimbal_UI_Tool_CN.md) | — |
| Zenoh 2D 包围盒 | [BBox 工具](Zenoh_BBox2D_CN.md) | — |
| RoamerX Lite 集成 | — | [Integration Guide](RoamerX_Lite_Integration.md) |
| Pixel Streaming | — | [Pixel Streaming 2](pixelstreaming_tutorial.md) |
| 高级配置 | [高级配置](Advanced_Configuration_CN.md) | — |
| Docker 状态 | — | [Docker Support Status](Docker_Tutorial.md) |
| 架构与发布 | — | [Maintainer Guide](MAINTAINER_GUIDE.md) |
| 故障排查 | [常见问题](FAQ_CN.md) | — |
| 发布变化 | [v1.0.13 发布说明](Release_Notes_CN.md) | — |

## 社区

<div align="center">
  <img src="../demo_gif/wechat.png" alt="GENISOM AI 微信助手二维码" style="height: 320px; width: auto; margin: 0 12px;"/>
  <p><em>扫码添加“新奇机器人”，备注 MATRiX 加入仿真社区。</em></p>
</div>

## 参与贡献

欢迎提交问题和文档改进。提交 PR 前请阅读[贡献指南](../CONTRIBUTING.md)；安全问题请按[安全策略](../SECURITY.md)私下报告。

## 致谢

- [MuJoCo-Unreal-Engine-Plugin](https://github.com/oneclicklabs/MuJoCo-Unreal-Engine-Plugin)
- [MuJoCo](https://github.com/google-deepmind/mujoco)
- [Unreal Engine](https://github.com/EpicGames/UnrealEngine)
- [CARLA](https://carla.org/)
