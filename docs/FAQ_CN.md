# 常见问题

[中文主页](README_CN.md) | [快速开始](Getting_Started_CN.md)

以下说明依据当前 `uesim` 源码与 MATRiX v1.0.5 文档整理。若问题只出现在某个发布包中，请同时核对该发布包的版本、平台和附带说明。

## 启动与显示

**Q：启动后黑屏或停留在空场景**

- 默认地图应为 `/Game/Maps/MainWorld.MainWorld`。
- Windows 使用 DX12/SM6，Linux 使用 Vulkan/SM6；先更新显卡驱动并确认硬件支持。
- 移除不兼容的 DLC 后重试，并查看日志中的 map load、pak mount 和 shader 错误。
- 若是 Pixel Streaming，先在本机窗口确认场景可以正常渲染，再排查信令服务器。

**Q：修改机器人配置后没有生效**

配置保存在 `Content/model/config/config.json`。保存后通过启动界面重新生成或重新启动机器人，使模型、传感器和运控实例重新创建。检查 JSON 是否有效，以及 `mujoco_model` 是否指向存在的 MJCF。

## Zenoh 与控制

**Q：收不到 `mujoco/state`**

- 确认 `zenoh_router` 是本机可监听或远端可连接的 endpoint。
- `state_port` 是字符串 key，不是数字端口；当前默认 key 为 `mujoco/state`。
- 确认机器人已经生成且 MuJoCo worker 正在推进。
- 跨机器连接时检查 Router 配置、防火墙和客户端 endpoint，不要把 `0.0.0.0` 当作远端目标地址。

**Q：机器人收不到控制命令**

- 默认命令 key 是 `mujoco/cmd`。
- 内置 motion core 当前使用本机 `tcp/127.0.0.1:7447` 以及固定的 `mujoco/state` / `mujoco/cmd`。
- 检查 `inside_mc`、机器人类型和策略资源是否匹配。
- Linux 模拟硬件模式通过共享内存连接外部 `mc_ctrl`，不是同一条 Zenoh 运控链路；不要同时启用两种控制源。

**Q：为什么 UDP 手柄和 Zenoh 都写 7447？**

UDP 手柄默认监听 `0.0.0.0:7447`，Zenoh endpoint 使用 TCP。TCP 与 UDP 是不同传输协议，可以使用相同端口号；这不表示二者消息格式或链路相同。

**Q：跳跃按键没有效果**

Jump（RB+X）与 FrontJump（RB+Y）只为 `xgb` 注册。其他 7 类内置运控模型目前只有 Passive、Stand 和 Walk。

## 传感器

**Q：当前支持哪些传感器？**

RGB、红外、深度、全景 RGB、鱼眼、通用 LiDAR、Mid-360、Airy、IMU、GPS 和里程计。旧 `wargb` / `wadepth` 已由 `fisheye` 取代，当前模板没有 `panoramadepth`。

**Q：深度图看起来几乎全白**

深度 PNG 不是普通彩色图。当前编码可按下式还原米制深度：

```text
depth_m = R + G / 255
```

其中 R、G 是通道值。若配置和接收端支持，也可使用原始 MDEP 负载。不要直接用照片查看器的亮度判断深度是否正确。

**Q：同步模式下为什么还有抖动？**

`sensor_sync_mode` 是机器人级开关。同步模式按频率分组调度；异步模式使用绝对 deadline，过载时记录实际采集时间并重新锚定，不会通过突发补帧追赶。500 Hz / 100 Hz / 10 Hz 是目标边界，实际频率仍受渲染、传感器和系统负载影响。

**Q：修改单个传感器的 `synchronized` 为什么无效？**

当前配置没有每传感器 `synchronized` 字段。请使用机器人级 `sensor_sync_mode`；旧 `synchronous_mode` 和 `synchronous_frequency` 也不再是当前保存格式。

## 地图与 DLC

**Q：DLC 应放在哪里？**

运行时递归扫描 `Saved/DLCs/*.pak` 与 `Content/DLCs/*.pak`。DLC 必须与平台、引擎和 MATRiX 版本兼容。

**Q：添加 DLC 后一定要重启吗？**

不一定。源码实现了启动扫描，也实现了运行时加载 DLC、枚举地图和打开地图。若当前发布包的界面没有暴露运行时入口，或挂载失败，重启是最简单的刷新方式。

**Q：为什么旧文档中的地图 ID 不工作？**

当前运行时按地图资产名称发现和打开地图，不应依赖旧的固定数字 ID。使用 `Town10World`、`YardWorld` 等实际名称，并以当前发布包列出的地图为准。

## 模型与坐标

**Q：可以加载自定义 MuJoCo 模型吗？**

可以。导入器支持运行时加载 MJCF/XML。将 `mujoco_model` 指向可访问且有效的 MJCF，并确保引用的 mesh、texture 等资源随模型一起提供。模型标识、模型目录和运控策略需要保持一致；自定义模型不会自动获得内置运动策略。

**Q：MuJoCo 与 Unreal 坐标如何转换？**

默认将 MuJoCo 米制右手坐标 `(x, y, z)` 转为 Unreal 左手坐标 `(x, -y, z)`，并使用 100 倍单位缩放。传感器挂到生成的 visual mesh 时还要考虑 body-to-geom 补偿；优先通过启动器的标准 Spawn 流程创建机器人。

## 工具与容器

**Q：文档中的 `Tools/` 在哪里？**

当前文档仓库和所核对的 `uesim` 源码快照都没有这些 Python 工具。它们只适用于确实附带 `Tools/` 的运行包；先运行脚本 `--help`，不要假设旧版参数仍然有效。

**Q：官方 Docker 脚本在哪里？**

当前源码与文档仓库没有可验证的 Dockerfile、镜像定义或 `scripts/docker`。因此不能把旧 Docker 教程视为当前官方工作流。详见 [Docker 状态说明](Docker_Tutorial.md)。

仍无法定位时，请保存平台、版本、`config.json`（移除密钥和私有地址）、复现步骤及相关日志，再通过 [Community](../README.md#-community) 获取支持。
