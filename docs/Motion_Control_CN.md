# 运动控制指南

[中文主页](README_CN.md) | [机器人与地图](Robots_and_Maps_CN.md) | [手柄控制](Controller_Guide_CN.md)

本文依据当前 `MatrixMotionControl` 与 MuJoCo 运行时代码整理。旧版文档中的 `mc_python/run.py` 和 `matrix_mc_unreal` 不属于当前所核对源码的标准启动链路。

## 控制架构

当前源码提供两种用途不同的控制方式：

| 模式 | 数据链路 | 适用场景 |
|---|---|---|
| 进程内运控 | UeSim ↔ Zenoh ↔ 内置 motion core | 直接在仿真进程内运行内置策略 |
| Linux 模拟硬件 | UeSim ↔ 共享内存 ↔ 外部 `mc_ctrl` | 让外部控制程序使用模拟硬件 ABI |

两种方式不应同时向同一个机器人写入控制命令。Linux 模拟硬件后端使用进程级共享资源，因此一个 UeSim 进程/容器只应承载一个使用该链路的机器人。

## 支持的模型

| 配置模型 | UI/协议名称 | 基本动作 | 扩展动作 |
|---|---|---|---|
| `xgb` | `xg` | Passive、Stand、Walk | Jump、FrontJump |
| `xg2` | `xg2` | Passive、Stand、Walk | — |
| `xgw` | `xgw` | Passive、Stand、Walk | — |
| `xgw2` | `xgw2` | Passive、Stand、Walk | — |
| `zgws` | `zgws` | Passive、Stand、Walk | — |
| `zgwt` | `zgwt` | Passive、Stand、Walk | — |
| `zgwsarm` | `zgws_arm` | Passive、Stand、Walk | — |

`go2` 与 `go2w` 有 MJCF 模型资产，但当前内置运控工厂没有为它们注册 motion core。

## 进程内运控

配置中的关键字段：

```json
{
  "robot": {
    "robot_type": "xgb",
    "mujoco_model": "xgb/scene.xml",
    "inside_mc": true,
    "zenoh_router": "tcp/127.0.0.1:7447",
    "state_port": "mujoco/state",
    "cmd_port": "mujoco/cmd"
  }
}
```

注意：

- 内置 motion core 当前要求本机 Zenoh endpoint `tcp/127.0.0.1:7447`。
- 插件内部使用固定 key `mujoco/state` 和 `mujoco/cmd`。配置中最好保持相同值，避免仿真和控制端订阅不同 key。
- 控制循环目标为 500 Hz，ONNX 推理目标为 100 Hz；实际频率会受渲染、模型和系统负载影响。
- `robot_type`、模型目录和策略类型必须匹配。

推荐启动顺序：

1. 确认本机 Zenoh Router 可在 `127.0.0.1:7447` 连接。
2. 在机器人配置中启用 `inside_mc`。
3. 选择受支持的模型并启动 UeSim。
4. 先进入 Stand，再进入 Walk；确认状态反馈稳定后再发送跳跃动作。

## Linux 模拟硬件模式

该模式由 UeSim 提供模拟硬件共享内存，再由外部 `mc_ctrl` 访问。它不是“通过 Zenoh 启动外部控制器”。

推荐顺序：

1. 启动启用了 simulated hardware 的 UeSim 和机器人。
2. 等待共享内存与机器人状态初始化完成。
3. 启动与当前机器人 ABI、模型和版本匹配的 `mc_ctrl`。
4. 停止时先让机器人进入安全状态，再退出外部控制器和仿真。

此后端只在 Linux 路径中实现。外部 `mc_ctrl` 的二进制、模型和参数不在当前文档仓库中，应以对应控制器发布包为准。

## 本地与 UDP 手柄输入

运控插件支持四种输入模式：

- `Hardware`：使用 Unreal 的逻辑 Gamepad 输入。
- `UDP`：接收 UDP JSON 手柄状态。
- `Auto`：按插件逻辑自动选择可用输入。
- `Disabled`：不接收手柄控制。

UDP 输入默认监听 `0.0.0.0:7447`。这是 UDP socket，可以与同端口号的 Zenoh TCP endpoint 共存，但二者不是同一协议。源码提供 `send_gamepad_udp.py` 作为发送端参考；发布包是否附带该脚本取决于打包内容。

## 默认动作映射

| 动作 | 输入 |
|---|---|
| 行走指令 | 左摇杆；A 进入 Walk |
| 偏航 | 右摇杆水平轴 |
| 站立 | Y |
| 被动/卸力 | LB + RB |
| 原地跳跃 | RB + X，仅 `xgb` |
| 向前跳跃 | RB + Y，仅 `xgb` |

动作切换前应确保机器人已稳定站立并留有安全空间。没有为某个模型注册的动作不会自动降级为相似动作。

## 排查

- 没有状态：确认 Router 地址、`mujoco/state` 和机器人是否已开始推进 MuJoCo。
- 没有动作：确认 `inside_mc`、模型名称、`mujoco/cmd` 和策略资源一致。
- 手柄无响应：检查输入模式是否为 `Hardware` / `Auto`，以及 Unreal 是否识别到逻辑 Gamepad 轴和按键。
- UDP 无响应：确认发送目标 IP、UDP 7447、防火墙以及 JSON 格式与当前发送脚本一致。
- 频率不足：降低渲染和传感器负载，并以实际时间戳和日志为准，不要假设目标频率一定达到。
