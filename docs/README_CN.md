<div align="center">

<p><a href="../README.md">English</a> | <strong>简体中文</strong></p>

# MATRiX

**基于 Unreal Engine、MuJoCo 的高保真机器人仿真平台**

<img src="../demo_gif/Forest.png" alt="MATRiX 高保真仿真环境" width="800"/>

[宣传片](#-宣传片) · [快速开始](#-快速开始) · [文档中心](#-文档) · [机器人与场景](Robots_and_Maps_CN.md) · [参与贡献](../CONTRIBUTING.md)

</div>

MATRiX 是一个即下即用的机器人仿真平台：Unreal Engine 提供高保真渲染，MuJoCo 运行机器人物理仿真，Zenoh 传输兼容 ROS 2 的传感器与控制数据。当前源码支持运行时加载 MJCF、动态传感器配置、内置运动控制和 DLC 地图发现；核心仿真流程无需安装 ROS。

> [!IMPORTANT]
> 当前版本为 **v1.0.5**。源码面向 64 位 Windows（DX12/SM6）与 Linux（Vulkan/SM6）；硬件和驱动要求可能随运行包变化，详见[快速开始指南](Getting_Started_CN.md)。

## 🎥 宣传片

<div align="center">
  <img src="../demo_gif/demo.gif" alt="MATRiX 2.0 高保真机器人仿真效果展示" width="800"/>
  <p>
    <strong>MATRiX 2.0 仿真效果宣传片</strong><br/>
    <sub>高保真场景 · 多机器人仿真 · 强化学习训练 · 真实场景重建</sub>
  </p>
</div>

## ✨ 核心能力

- **运行时 MuJoCo 集成：** 运行时加载 MJCF/XML，通过独立 worker 推进物理仿真，默认目标频率为 500 Hz。
- **完整传感器栈：** 支持 RGB、红外、深度、鱼眼、全景、通用 LiDAR、Mid360、Airy、IMU、GPS 和里程计，并使用统一的 ROS 2 时间戳模型。
- **内置运动控制：** 内置 `xgb`、`xg2`、`xgw`、`xgw2`、`zgws`、`zgwt`、`zgwsarm` 运控核心，并提供 Linux 共享内存模拟硬件链路。
- **运行时地图 DLC：** 自动发现 `Saved/DLCs` 与 `Content/DLCs`，既可启动时挂载，也可在运行中加载。
- **Zenoh 与局域网同步：** 通过 Zenoh 发布兼容 ROS 2 CDR 的数据，控制键固定为 `mujoco/state` 与 `mujoco/cmd`，并可选启用局域网状态/事件同步。
- **图形化配置：** 启动器通过 JSON 配置机器人、地图、初始位置、联网方式、运动控制和动态传感器数组。

## 🎬 仿真效果展示

<div align="center">
<table>
<tr>
<td align="center"><img src="../demo_gif/Town10.gif" alt="Town10 城市场景" width="360"/><br/><sub>Town10 城市场景</sub></td>
<td align="center"><img src="../demo_gif/Venice.gif" alt="Venice 水城场景" width="360"/><br/><sub>Venice 水城场景</sub></td>
</tr>
<tr>
<td align="center"><img src="../demo_gif/whmap.gif" alt="仓库场景" width="360"/><br/><sub>仓库场景</sub></td>
<td align="center"><img src="../demo_gif/Yardmap.gif" alt="庭院场景" width="360"/><br/><sub>庭院场景</sub></td>
</tr>
</table>
</div>

## 🚀 快速开始

1. 下载运行包：[Linux（提取码：`6sth`）](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth)或 [Windows（提取码：`s9iy`）](https://pan.baidu.com/s/1JTMi2H8WMC2T8_8fbspjzA?pwd=s9iy)。
2. 按需下载地图 DLC，并将 `.pak` 文件放入 `Windows/UeSim/Saved/DLCs/`。
3. 在 Windows 上启动 MATRiX：

~~~powershell
.\Windows\UeSim\Binaries\Win64\UeSim.exe
~~~

启动后即可在界面中选择机器人、场景并配置传感器。完整的平台要求、目录说明和工具验证步骤见[快速开始指南](Getting_Started_CN.md)。

如果下载的运行包附带可选的 `Tools/` 目录，可按典型方式启动接收器：

~~~powershell
pip install eclipse-zenoh opencv-python numpy
cd Tools
python zenoh_sensor_receiver.py
~~~

## 📚 文档

| 主题 | 文档 |
|---|---|
| 安装与启动 | [快速开始](Getting_Started_CN.md) |
| 机器人与场景 | [中文](Robots_and_Maps_CN.md) · [English](Robots_and_Maps.md) |
| 传感器与 Zenoh | [传感器与通信](Sensor_and_Communication_CN.md) |
| 传感器配置 | [传感器配置详解](Sensor_Config_Tutorial.md) |
| 数据工具 | [Python 工具](Python_Tools_CN.md) |
| 运动控制 | [运动控制指南](Motion_Control_CN.md) |
| 遥控器与控制 | [中文](Controller_Guide_CN.md) · [English](Controller_Guide.md) |
| 手动配置 | [高级配置](Advanced_Configuration_CN.md) |
| 架构与维护 | [维护者指南（英文）](MAINTAINER_GUIDE.md) |
| 故障排查 | [常见问题](FAQ_CN.md) |
| Docker | [Docker 支持状态](Docker_Tutorial.md) |
| Pixel Streaming | [浏览器远程查看指南](pixelstreaming_tutorial.md) |
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
