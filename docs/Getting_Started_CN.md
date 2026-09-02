# 快速开始

[English README](../README.md) | [中文主页](README_CN.md)

本文依据当前 `uesim` 源码与 MATRiX v1.0.5 文档仓库整理。源码可以验证运行时配置、插件和启动行为；具体下载包的显卡驱动、系统依赖和附带工具仍以该发布包说明为准。

## 1. 平台与图形接口

当前工程和关键插件面向以下目标：

- Windows 64 位：DirectX 12 / Shader Model 6
- Linux 64 位：Vulkan / Shader Model 6

建议使用支持对应图形接口的独立显卡，并安装最新稳定版驱动。源码没有定义统一的最低 CPU、内存或显存门槛，因此不要把某一台开发机的配置当作官方最低要求。

## 2. 获取运行包

从项目发布页下载与你的平台匹配的 MATRiX 运行包和所需地图 DLC：

- [GitHub Releases](https://github.com/GENISAMA/MATRiX/releases)
- [项目主页](https://matrix.genesilico.cn/)

解压到不含特殊权限限制的目录。文档仓库本身不包含可执行程序；若运行包提供 `Tools/`、控制器或其他辅助目录，以运行包内的说明为准。

## 3. 运行时关键目录

不同发布包的顶层布局可能略有差异，但源码使用的核心位置如下：

```text
<runtime>/
├── Content/
│   ├── model/
│   │   ├── config/config.json
│   │   └── {go2,go2w,xgb,xg2,xgw,xgw2,zgws,zgwt,zgwsarm}/
│   └── DLCs/*.pak
├── Saved/
│   └── DLCs/*.pak
└── [optional] Tools/
```

- 默认机器人配置：`Content/model/config/config.json`
- 基础地图：`MainWorld`
- DLC 搜索位置：`Saved/DLCs/` 和 `Content/DLCs/`，包含子目录
- `Tools/`：仅部分运行包附带，不属于当前文档仓库或所核对的 `uesim` 源码

## 4. 启动仿真器

1. 启动发布包中的 MATRiX / UeSim 可执行程序。
2. 在启动界面选择机器人、地图、网络模式和传感器。
3. 检查模型路径和 Zenoh Router 配置。
4. 启动仿真。

未额外选择 DLC 时，工程默认进入 `MainWorld`。默认配置使用 `xgb` 模型，Zenoh Router 为 `tcp/0.0.0.0:7447`，状态和命令 key 分别为 `mujoco/state` 与 `mujoco/cmd`。

> `state_port` 和 `cmd_port` 是历史字段名，当前保存的是字符串消息 key，不是数字 UDP 端口。

## 5. 安装与切换地图

将与当前平台和版本匹配的 `.pak` 放入：

```text
Saved/DLCs/
```

也可以使用源码支持的：

```text
Content/DLCs/
```

启动时系统会扫描并挂载 DLC；界面也实现了运行时加载和打开已安装地图的能力。若某个发布包没有暴露运行时加载入口，重启仿真器是最简单的刷新方式，但不是源码层面的强制要求。

地图名称、打包列表和预览见 [机器人与地图](Robots_and_Maps_CN.md)。

## 6. 配置机器人与传感器

图形界面保存的机器人配置采用以下结构：

```json
{
  "robot": {
    "robot_type": "xgb",
    "mujoco_model": "xgb/scene.xml",
    "network_mode": "standalone",
    "sensor_sync_mode": false,
    "inside_mc": false,
    "zenoh_router": "tcp/0.0.0.0:7447",
    "state_port": "mujoco/state",
    "cmd_port": "mujoco/cmd",
    "sensors": {}
  }
}
```

当前源码覆盖 RGB、红外、深度、全景、鱼眼、通用 LiDAR、Mid-360、Airy、IMU、GPS 和里程计。修改配置后，应通过启动界面重新生成或重新启动机器人，使新的模型和传感器实例生效。

详细说明：

- [高级配置](Advanced_Configuration_CN.md)
- [传感器与通信](Sensor_and_Communication_CN.md)
- [传感器配置教程（英文）](Sensor_Config_Tutorial.md)

## 7. 启用运动控制

当前公开文档列出 7 类内置机器人运控：`xgb`、`xg2`、`xgw`、`xgw2`、`zgws`、`zgwt`、`zgwsarm`。

- `inside_mc: true`：使用进程内运控核心。
- Linux 模拟硬件模式：通过共享内存连接外部 `mc_ctrl`。
- 两种方式是不同的控制链路，不应同时驱动同一机器人。

内置控制循环目标为 500 Hz，ONNX 推理目标为 100 Hz。完整的模型映射、Zenoh 前置条件、手柄动作与安全限制见 [运动控制指南](Motion_Control_CN.md)。

## 8. 首次通信检查

传感器和机器人状态使用 Zenoh 传输 ROS 2 兼容的 CDR 负载。常用 key 包括：

```text
mujoco/state
mujoco/cmd
rt/camera/image/compressed
rt/front_lidar
```

实际 key 可在传感器配置中覆盖。若下载包包含 `Tools/`，可使用其中的话题监控或接收器；先运行对应脚本的 `--help`，因为这些工具不在当前源码快照中，参数可能随发布包变化。

## 9. 下一步

- [运动控制](Motion_Control_CN.md)
- [手柄与相机控制](Controller_Guide_CN.md)
- [Python 工具说明](Python_Tools_CN.md)
- [常见问题](FAQ_CN.md)
