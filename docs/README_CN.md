<div align="center">

<p><a href="../README.md">English</a> | <strong>简体中文</strong></p>

# MATRiX

**基于 Unreal Engine、MuJoCo 的高保真机器人仿真平台**

<img src="../demo_gif/Forest.png" alt="MATRiX 中四足机器人探索高保真森林场景" width="800"/>

[核心优势](#核心优势) · [宣传片](#-宣传片) · [快速开始](#-快速开始) · [文档中心](#-文档) · [机器人与场景](Robots_and_Maps_CN.md)

</div>

MATRiX 是一个面向运行时工作流的机器人仿真平台，将 Unreal Engine 5 渲染与 MuJoCo 动力学整合到同一套流程中。用户可以直接加载 MJCF/XML 机器人、组合经过标定的虚拟传感器、使用内置运控，并通过 Zenoh 传输兼容 ROS 2 的数据；核心仿真器无需安装 ROS 2。

> [!IMPORTANT]
> 当前版本为 **v1.0.13**，提供 Linux x86_64 运行包。正确安装显卡驱动后即可运行，仿真器不限定 Ubuntu 22.04。只有另行下载的可选独立运控限定 Ubuntu 22.04 x86_64。

## 核心优势

| 从模型到算法 | MATRiX 提供的能力 |
|---|---|
| **更快接入机器人** | 运行时直接加载 MJCF/XML，通过 JSON 配置机器人、初始位姿、传感器、话题和控制模式，无需为每个模型重新构建仿真器。 |
| **用更真实的传感器测试感知算法** | 支持 RGB、红外、GPU 深度、全景、鱼眼、通用 LiDAR、Mid360、Airy、IMU、GPS 和里程计；仿真链路包含相机内参、Brown-Conrady/Kannala-Brandt 畸变、LiDAR 扫描时序和运动畸变。 |
| **保证多传感器时间一致性** | 统一时间系统支持稳定 UTC、Unreal 仿真时间、外部 `/clock` 和固定步长；相机与 LiDAR 可加入同一硬件式触发组，共享触发序列与时间戳。 |
| **从仿真控制平滑过渡到控制器联调** | MuJoCo 在独立 worker 上运行，目标控制频率 500 Hz；默认内置运控开箱即用，可选外部 `robot_mc` 复用同一模拟硬件 ABI；关节与执行器目标由当前 MuJoCo 模型限位。 |
| **无需 ROS 依赖也能使用 ROS 兼容数据** | Zenoh 发布兼容 ROS 2 CDR 的压缩图像、`PointCloud2` 等消息；仿真器可独立运行，ROS 2 bridge 按需接入。 |
| **地图内容与基础包独立扩展** | 启动界面可更新经过校验的远程地图目录、识别已挂载内容并按需下载 DLC；标准 UE 场景、动态角色、Gaussian Splatting 和 Pixel Streaming 2 共用同一运行时。 |
| **随包提供完整调试工具** | `Tools/` 包含传感器接收、话题监控、LiDAR-相机投影、2D/3D 包围盒、云台控制、运控 UDP、Spawn 和语音消息测试工具。 |

## 🎥 宣传片

<div align="center">
  <img src="../demo_gif/demo.gif" alt="在 MATRiX 中选择机器人并启动仿真" width="800"/>
  <p>
    <strong>MATRiX 2.0 仿真效果宣传片</strong><br/>
    <sub>机器人选择 · 高保真场景 · 多机器人仿真 · 强化学习训练 · 真实场景重建</sub>
  </p>
</div>

## ✨ 核心能力

- **运行时机器人接入：** 加载 MJCF/XML、自定义模型、绑定视觉/碰撞资源并复用传感器方案，不需要为每个机器人制作独立运行包。
- **高频物理与控制：** 独立 MuJoCo 仿真 worker、目标 500 Hz 控制/硬件循环、命令超时保护，以及从模型读取的关节和执行器限位。
- **可标定的感知仿真：** GPU SceneDepth、异步 GPU 回读和编码、透视/鱼眼镜头模型、同步采集，以及 LiDAR 逐点时间与运动畸变。
- **开放的数据平面：** Zenoh 发布/订阅、兼容 ROS 2 的消息布局、可配置 key expression、统一时间戳和可选局域网状态/事件同步。
- **灵活的运控架构：** 默认内置运控开箱即用；也可通过一个配置开关切换到另行下载的独立运控，并复用原版共享内存硬件接口。
- **可扩展环境：** 地图目录动态更新、DLC 自动下载与挂载、运行时地图检测、Gaussian Splatting、动态人车和 Pixel Streaming 2。
- **面向开发者的工作流：** JSON 与图形化传感器配置，以及覆盖数据检查、投影、包围盒、云台和协议联调的 Linux 工具链。

### 适用方向

- 感知、SLAM、传感器融合和合成数据开发；
- 运动控制、全身控制、强化学习和控制器回归测试；
- 上实机前的模拟硬件与外部运控联调；
- 多场景验证、远程演示和浏览器可视化。

## 🎬 仿真效果展示

<div align="center">
<table>
<tr>
<td align="center"><img src="../demo_gif/Town10.gif" alt="四足机器人在 Town10 城市道路运动" width="360"/><br/><sub>Town10 · 城市道路运动</sub></td>
<td align="center"><img src="../demo_gif/Venice.gif" alt="Venice 场景的 RGB 与传感器视图" width="360"/><br/><sub>Venice · RGB 与传感器可视化</sub></td>
</tr>
<tr>
<td align="center"><img src="../demo_gif/whmap.gif" alt="机器人在明暗变化明显的仓库场景中运动" width="360"/><br/><sub>仓库 · 工业场景与动态光照</sub></td>
<td align="center"><img src="../demo_gif/Yardmap.gif" alt="四足机器人在庭院台阶附近运动" width="360"/><br/><sub>庭院 · 台阶附近运动</sub></td>
</tr>
</table>
</div>

## 🚀 快速开始

1. 任选一种方式下载 MATRiX v1.0.13：
   - [GitHub Release](https://github.com/zsibot/matrix/releases/tag/v1.0.13)：下载全部 3 个压缩分片和 `SHA256SUMS`，保持原文件名并放在同一目录；
   - [百度网盘 Linux 运行包](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q)：提取码 `118g`。
2. 使用 GitHub 分片时，先校验并解压：

~~~bash
sha256sum -c SHA256SUMS
cat MATRiX_v1.0.13.tar.gz.part-* | tar -xzf -
~~~

3. 启动 MATRiX：

~~~bash
cd MATRiX_v1.0.13
./UeSim.sh
~~~

压缩包已保留可执行权限，不需要对 `UeSim.sh` 或 `UeSim/Binaries/Linux/UeSim` 执行 `chmod`。

默认启用内置运控（`robot.inside_mc=true`），无需启动额外控制器进程。开源运行包不包含独立 `robot_mc`；确需使用时，从 [MATRiX_Robot_MC](https://github.com/GENISOM-AI/MATRiX_Robot_MC/releases) 下载受支持的 Linux 运行包，并按[运动控制指南](Motion_Control_CN.md)配置。

在地图选择界面先点击 **UPDATE LIST（更新列表）**，再点击目标地图下方的 **DOWNLOAD（下载）**。手动安装时，从[地图 DLC 百度网盘](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F)下载，提取码 `6sth`，具体步骤见[地图与 DLC](Map_DLC_CN.md)。

如果运行包包含 `Tools/`，可按典型方式启动传感器接收器：

~~~bash
python3 -m pip install eclipse-zenoh opencv-python numpy
python3 Tools/zenoh_sensor_receiver.py
~~~

完整平台要求、目录说明和工具验证步骤见[快速开始指南](Getting_Started_CN.md)。

## 📚 文档

| 主题 | 文档 |
|---|---|
| 安装与启动 | [中文](Getting_Started_CN.md) · [English](Getting_Started.md) |
| Release 下载与校验 | [中文](Release_Download_CN.md) · [English](Release_Download.md) |
| 机器人与场景 | [中文](Robots_and_Maps_CN.md) · [English](Robots_and_Maps.md) |
| 地图与 DLC | [中文](Map_DLC_CN.md) · [English](Map_DLC.md) |
| 传感器与 Zenoh | [传感器与通信](Sensor_and_Communication_CN.md) |
| 传感器配置 | [传感器配置详解](Sensor_Config_Tutorial.md) |
| 数据工具 | [Python 工具](Python_Tools_CN.md) |
| LiDAR 到相机投影 | [中文](Lidar_Camera_Projection_CN.md) · [English](Lidar_Camera_Projection.md) |
| 运动控制 | [中文](Motion_Control_CN.md) · [English](Motion_Control.md) |
| 遥控器与控制 | [中文](Controller_Guide_CN.md) · [English](Controller_Guide.md) |
| 手动配置 | [高级配置](Advanced_Configuration_CN.md) |
| 架构与维护 | [维护者指南（英文）](MAINTAINER_GUIDE.md) |
| 故障排查 | [常见问题](FAQ_CN.md) |
| Docker | [Docker 支持状态](Docker_Tutorial.md) |
| Pixel Streaming | [浏览器远程查看指南](pixelstreaming_tutorial.md) |
| 版本变化 | [v1.0.13 发布说明](Release_Notes_CN.md) |
| 英文项目首页 | [English](../README.md) |

## 💬 社区

**添加 GENISOM AI 微信助手，参与 MATRiX 仿真讨论并获取支持：**

<div align="center">
  <img src="../demo_gif/wechat.png" alt="GENISOM AI 微信助手二维码" style="height: 320px; width: auto; margin: 0 12px;"/>
  <p><em>扫码添加“新奇机器人”，备注 MATRiX 即可加入仿真社区。</em></p>
</div>

## 🤝 参与贡献

欢迎提交问题报告、文档改进和运行工具修改。开始前请阅读[贡献指南](../CONTRIBUTING.md)，修改启动或发布脚本前请查看[架构与维护说明](MAINTAINER_GUIDE.md)。安全问题请按照[安全策略](../SECURITY.md)私下报告，不要提交公开 Issue。

## 🙏 致谢

本项目基于以下优秀的开源项目构建：

- [MuJoCo-Unreal-Engine-Plugin](https://github.com/oneclicklabs/MuJoCo-Unreal-Engine-Plugin)
- [MuJoCo](https://github.com/google-deepmind/mujoco)
- [Unreal Engine](https://github.com/EpicGames/UnrealEngine)
- [CARLA](https://carla.org/)
