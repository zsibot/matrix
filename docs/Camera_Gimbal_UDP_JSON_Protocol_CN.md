# UeSim 摄像头云台 UDP/JSON 控制协议

## 文档信息

| 项目 | 内容 |
| --- | --- |
| 文档编号 | `UESIM-GIMBAL-UDP-001` |
| 文档版本 | `1.1.1` |
| 协议名称 | `uesim.gimbal` |
| 协议版本 | `1.1` |
| 传输协议 | UDP/IPv4 单播 |
| 数据编码 | UTF-8 JSON |
| 发布状态 | 对外交付基线；UeSim 实现已通过编译和自动化测试 |
| 发布日期 | 2026-08-11 |
| 默认控制端口 | UDP `8870`（UeSim 服务端监听） |
| 默认状态接收端口 | UDP `8871`（外部客户端本地绑定） |

### 修订记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| `1.0` | 2026-08-11 | 首次发布：定义UDP端点、JSON封装、控制命令、应答、错误码、幂等、控制者租约和安全约束 |
| `1.0.1` | 2026-08-11 | 明确查询式状态链路中的默认端口 |
| `1.1` | 2026-08-12 | 删除`get_state`命令，改为服务端默认10Hz主动发布状态；状态端口在PTZ生成时配置 |
| `1.1.1` | 2026-08-12 | 完善对外交付配置、蓝图映射、启动流程、字段作用域和联调验收说明；线协议仍为`1.1` |

## 1. 范围

本文档定义外部控制器与 UeSim 摄像头两轴云台之间的 UDP/JSON 控制接口，包括：

- UDP 监听端口和服务生命周期。
- JSON 数据报封装格式。
- 请求、应答和错误格式。
- 速度、方向、角度、点动、粗调、微调、防抖及主动状态发布。
- 速度指令固定 `0.1 秒`有效期。
- UDP 丢包、重复包、乱序包和重试规则。
- 输入范围、单位、错误码和安全约束。

本文档不定义：

- 图像、深度图或视频数据传输。
- 云台真实硬件的串口、CAN、ONVIF 或厂商私有协议。
- 用户认证、加密或公网传输。
- UDP 服务的远程启动和远程关闭。

## 2. 规范用语

本文档中的用语含义如下：

- “必须”：协议实现不可省略的要求。
- “禁止”：协议实现不可执行的行为。
- “应”：推荐行为；若不采用，需要有明确兼容性理由。
- “可以”：可选能力。

除非字段说明另有规定，JSON 字段名称、字符串枚举值和命令名称均区分大小写。

### 2.1 交付文件

交付包中与云台直接相关的文件如下：

| 文件 | 用途 |
| --- | --- |
| `Content/model/config/sensors/config_ptzrgb.json` | PTZRGB独立传感器配置示例 |
| `docs/Camera_Gimbal_UDP_JSON_Protocol_CN.md` | 本协议，外部控制器开发依据 |
| `Tools/gimbal_udp_client.py` | 命令行控制及状态监听参考实现 |
| `Tools/gimbal_udp_ui.py` | 上下左右控制及状态显示测试工具 |

外部系统只需要实现本协议定义的 UDP/JSON 控制和状态接收，不需要依赖 Unreal 蓝图或项目源码。

### 2.2 PTZRGB传感器配置

独立传感器配置示例：

```json
{
  "camera": {
    "sensor_type": "ptzrgb",
    "ignore_mounting_actor": false,
    "topic": "/front_camera/image/compressed",
    "frequency": 10,
    "position": {"x": 0.0, "y": 0.0, "z": 0.15},
    "rotation": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
    "height": 1080,
    "width": 1920,
    "fov": 120,
    "sensor_attach": "base_link",
    "control_port": 8870,
    "state_port": 8871,
    "stablization": true
  }
}
```

也可以把同一个`camera`对象放在机器人配置的`robot.sensors.camera`路径下。PTZ专用字段定义：

| 字段 | 类型 | 缺省值 | 约束 | 说明 |
| --- | --- | ---: | --- | --- |
| `sensor_type` | String | 无 | 固定`ptzrgb` | 选择可控云台RGB传感器 |
| `control_port` | Integer | `8870` | `1024～65535` | UeSim监听控制请求的UDP端口 |
| `state_port` | Integer | `8871` | `1024～65535`且不得等于`control_port` | 状态客户端绑定的UDP接收端口 |
| `stablization` | Boolean | `false` | `true`或`false` | 启动时是否启用`FollowDamping`防抖 |

部署配置保留历史拼写`stablization`。读取器兼容`stabilization`别名，但保存时统一输出`stablization`。`frequency`是RGB图像发布频率；云台状态发布频率固定默认`10Hz`，二者互不影响。

以下字段是 UeSim 内部运行时 Spawn 桥字段，不属于对外配置，用户禁止写入 JSON：

```text
GimbalControlPort
GimbalStatePublishPort
GimbalStatePublishRateHz
bStartGimbalOnBeginPlay
bEnableGimbalStabilizationOnStart
```

如果旧配置包含这些字段，当前读取器会忽略，下一次保存时会删除。运行时会从`control_port`、`state_port`和`stablization`自动派生所需 Spawn 参数。

### 2.3 蓝图读取与启动流程

`Break Mujoco Sensor Config`节点直接输出以下对外字段：

```text
Control Port (control_port)
State Port (state_port)
Stabilization (stablization)
```

配置驱动的`ptzrgb`生成流程为：

```text
读取配置
  -> Sensor Type == "ptzrgb"
  -> Spawn BP_PTZCamera
  -> 应用 Control Port / State Port / Stabilization
  -> 自动启动云台UDP服务
  -> 默认10Hz主动发布云台状态
```

`stablization=true`时，云台启动后使用`FollowDamping`模式；为`false`时使用`Off`。配置驱动生成时不需要用户再添加内部 Spawn 字段。

云台服务与RGB图像采集是两个独立生命周期：`StartGimbal`负责运动控制和状态发布，`StartSensor`负责图像采集。手工搭建蓝图时必须分别调用；仅调用`StartGimbal`不会产生RGB图像，仅调用`StartSensor`也不会开放云台UDP控制。

### 2.4 `state_port`字段作用域

完整机器人配置中可能存在两个同名字段：

| JSON路径 | 类型 | 示例 | 作用 |
| --- | --- | --- | --- |
| `robot.state_port` | String | `"mujoco/state"` | 机器人运控状态的Zenoh Key表达式 |
| `robot.sensors.camera.state_port` | Integer | `8871` | PTZ云台主动状态消息的UDP目标端口 |

两者协议、类型和用途不同，禁止互换。本协议中的`state_port`始终指 PTZ 传感器对象内的整数 UDP 端口。

## 3. 服务模型

### 3.1 控制端口与状态接收端口

- 每个云台实例独占一个 UDP/IPv4 控制监听端口，默认`control_port=8870`。
- 同一主机上的多个云台必须配置不同端口。
- 一个 UDP 数据报只能控制接收该数据报的云台实例。
- 协议 v1.1 不支持一个共享端口路由到多台云台。
- Socket 禁止启用允许多个云台同时绑定同一地址和端口的端口复用行为。

默认端口角色：

| 配置字段 | 默认值 | 绑定方 | 作用 |
| --- | ---: | --- | --- |
| `control_port` | UDP `8870` | UeSim 云台服务端 | 接收控制命令，并向命令源返回应答 |
| `state_port` | UDP `8871` | 外部状态客户端 | 接收 UeSim 默认10Hz主动发布的状态消息 |

`state_port=8871`是状态消息的目标端口，不是 UeSim 的接收端口。UeSim 启动云台后无需状态请求，按默认`10Hz`主动向`state_target_address:state_port`发送状态消息。

```text
控制客户端 ClientIP:any   -- control request --> UeSimIP:8870
状态客户端 ClientIP:8871  <-- state @ 10 Hz ----- UeSimIP:8870
```

默认状态目标地址为`127.0.0.1`。服务端收到来自远程主机的合法 v1.1 控制协议包后，状态目标地址更新为该主机 IP，端口始终使用 Spawn 时配置的`state_port`。同一时刻每个云台只向一个目标地址发布状态。

同一主机上的多台云台必须使用不同的`control_port`。多台云台可以向同一个`state_port`发送状态，由一个接收程序按`gimbal_id`分流；若每台云台使用独立监听进程，建议为每台配置不同的`state_port`。每个云台自身的控制端口和状态端口不得相同。

### 3.2 本地启动接口

UDP 服务由 UeSim 本地蓝图或 C++启动：

```cpp
StartGimbal(
    int32 UdpListenPort,
    FString& OutError,
    int32 StatePublishPort = 8871,
    FString BindAddress = "127.0.0.1",
    FString StateTargetAddress = "127.0.0.1",
    float StatePublishRateHz = 10.0);
```

手工调用时必须提供控制端口；状态端口未连接时使用默认`8871`。配置驱动生成时，UeSim会把`control_port`和`state_port`解析为该接口的实际参数。

端口要求：

```text
1024 <= UdpListenPort <= 65535
1024 <= StatePublishPort <= 65535
UdpListenPort != StatePublishPort
0.1 <= StatePublishRateHz <= 100
```

绑定地址示例：

| 地址 | 含义 |
| --- | --- |
| `127.0.0.1` | 仅允许本机访问，推荐默认值 |
| 指定网卡 IPv4，如`192.168.1.20` | 仅监听指定网卡 |
| `0.0.0.0` | 监听所有 IPv4 网卡，必须配合防火墙和可信网络 |

启动成功后，云台进入 Running 状态，开始接收 UDP 控制消息，并立即按配置频率主动发布状态。

### 3.3 本地停止接口

UDP 服务由 UeSim 本地蓝图或 C++停止：

```cpp
StopGimbal();
```

停止必须执行：

1. 停止接收新 UDP 数据报。
2. 关闭并释放 Socket。
3. 清空尚未处理的接收队列。
4. 清空客户端 session、序列号和幂等应答缓存。
5. 取消速度和位置控制目标。
6. 将实际角速度立即置零并保持当前角度。
7. 重置防抖滤波器状态。

停止云台功能不停止摄像头传感器采集。相机继续以最后保持的云台角度采集。

### 3.4 启动幂等规则

- 已停止时调用`StartGimbal`：尝试创建并绑定 Socket。
- 已在相同控制地址、控制端口、状态端口、状态目标地址和发布频率运行时再次调用：返回`AlreadyRunningSameEndpoint`，不重建 Socket，不清除控制状态。
- 上述任一启动参数不同时再次调用：返回`AlreadyRunningDifferentEndpoint`，不自动切换配置。
- 切换端口必须先调用`StopGimbal`，再调用`StartGimbal`。
- 地址无效、端口无效或端口被占用时，启动失败，云台保持 Stopped 状态。
- Actor EndPlay 或销毁时必须自动执行等价的停止清理。

### 3.5 UDP不能远程启停服务

协议 v1.1 不提供远程`start_service`或`stop_service`命令。原因如下：

- Socket 尚未启动时无法接收远程启动命令。
- 远程关闭会使后续应答和恢复不可达。
- 未认证 UDP 不适合暴露服务生命周期管理能力。

`stop_motion`只停止云台运动，不关闭 UDP 服务。

## 4. 网络传输约定

### 4.1 基本约定

| 项目 | 规定 |
| --- | --- |
| IP版本 | IPv4 |
| 传输 | UDP单播 |
| 字节编码 | UTF-8，无BOM |
| 数据报内容 | 一个完整JSON对象 |
| 应用层分片 | 不支持 |
| 广播/组播 | v1.1不支持 |
| 应答目标 | 请求数据报的源IP和源端口 |
| 默认服务端控制端口 | UDP `8870` |
| 默认客户端状态接收端口 | UDP `8871` |

一个 UDP 数据报中禁止包含多个 JSON 对象，禁止发送 JSON 数组作为根节点，禁止跨多个数据报拆分一个 JSON 对象。

### 4.2 数据报大小

- 接收端必须拒绝大于`4096`字节的控制数据报。
- 发送端应将数据报控制在`1200`字节以内，降低 IP 分片概率。
- 状态发布消息和能力应答也应保持在`4096`字节以内。
- 禁止在 JSON 中放置图片、音频、Base64 二进制或大数组。

### 4.3 JSON约束

- 根节点必须是 JSON Object。
- 数值必须是 JSON Number，禁止用字符串代替数值。
- 布尔值必须使用`true`或`false`，禁止使用`0/1`或字符串。
- 禁止 NaN、Infinity 和负 Infinity。
- JSON 整数必须处于 JavaScript 安全整数范围：

```text
-9007199254740991 <= value <= 9007199254740991
```

- 必填字段不能为`null`。
- 同一 Object 内禁止出现重复字段名。
- 未识别的顶层扩展字段可以忽略。
- 命令`params`中的未知字段必须返回`UNKNOWN_PARAMETER`，用于尽早发现拼写错误。

## 5. 请求封装

### 5.1 通用请求结构

```json
{
  "protocol": "uesim.gimbal",
  "version": "1.1",
  "type": "request",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "client_id": "operator-console-01",
  "session_id": "cfe2d3ad-8020-46e5-97e0-41adf69b53e8",
  "sequence": 1,
  "gimbal_id": "camera_gimbal",
  "command": "ping",
  "reply_required": true,
  "client_time_ms": 1786387200000,
  "params": {}
}
```

### 5.2 请求字段

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `protocol` | String | 是 | 固定`uesim.gimbal` | 协议标识 |
| `version` | String | 是 | 当前固定`1.1` | 协议版本 |
| `type` | String | 是 | 固定`request` | 消息类型 |
| `request_id` | String | 是 | 1～64字符 | 请求唯一标识，推荐UUID |
| `client_id` | String | 是 | 1～64字符 | 客户端稳定标识 |
| `session_id` | String | 是 | 1～64字符 | 客户端进程或连接会话标识，推荐UUID |
| `sequence` | Integer | 是 | 1～2^53-1 | session内严格递增序号 |
| `gimbal_id` | String | 是 | 1～64字符 | 目标云台标识 |
| `command` | String | 是 | 见命令表 | 命令名称 |
| `reply_required` | Boolean | 否 | 默认`true` | 是否要求应答 |
| `client_time_ms` | Integer | 否 | Unix UTC毫秒 | 仅用于诊断，不参与超时和排序 |
| `params` | Object | 是 | 由命令定义 | 命令参数 |

`request_id`、`client_id`、`session_id`和`gimbal_id`应只使用以下字符：

```text
A-Z a-z 0-9 . _ : -
```

### 5.3 gimbal_id

- 云台必须配置稳定的`GimbalId`，不能依赖运行时 Actor 临时名称。
- 当前`BP_PTZCamera`默认`GimbalId`为`camera_gimbal`，本文及随附脚本均使用该默认值。
- PTZ JSON配置当前不提供`gimbal_id`字段；如项目方在蓝图类默认值或 Spawn 流程中修改`GimbalId`，外部控制器和状态监听器必须同步使用修改后的值。
- 普通控制请求的`gimbal_id`必须与接收端配置完全一致。
- `ping`和`get_capabilities`允许使用`"*"`，服务端应在应答中返回实际`gimbal_id`。
- 标识不匹配时禁止执行命令，并返回`GIMBAL_ID_MISMATCH`。

### 5.4 reply_required

- 省略时默认为`true`。
- `true`：服务端必须返回成功或失败应答。
- `false`：服务端不返回应答，包括参数错误应答。
- `ping`和`get_capabilities`无论该字段取值如何都必须应答。
- 离散命令，如`step`和`set_angle`，应使用`true`。
- 高频`set_velocity`可以使用`false`减少应答流量。

## 6. 应答封装

### 6.1 成功应答

```json
{
  "protocol": "uesim.gimbal",
  "version": "1.1",
  "type": "response",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "client_id": "operator-console-01",
  "session_id": "cfe2d3ad-8020-46e5-97e0-41adf69b53e8",
  "sequence": 1,
  "gimbal_id": "camera_gimbal",
  "command": "ping",
  "status": "ok",
  "code": 0,
  "error": "OK",
  "message": "",
  "server_time_ms": 1786387200012,
  "data": {}
}
```

### 6.2 错误应答

```json
{
  "protocol": "uesim.gimbal",
  "version": "1.1",
  "type": "response",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "client_id": "operator-console-01",
  "session_id": "cfe2d3ad-8020-46e5-97e0-41adf69b53e8",
  "sequence": 1,
  "gimbal_id": "camera_gimbal",
  "command": "set_angle",
  "status": "error",
  "code": 1006,
  "error": "OUT_OF_RANGE",
  "message": "pitch_deg must be between -60 and 60 degrees",
  "server_time_ms": 1786387200012,
  "data": {}
}
```

### 6.3 应答字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `protocol` | String | 固定`uesim.gimbal` |
| `version` | String | 固定`1.1` |
| `type` | String | 固定`response` |
| `request_id` | String | 原样回显 |
| `client_id` | String | 原样回显 |
| `session_id` | String | 原样回显 |
| `sequence` | Integer | 原样回显 |
| `gimbal_id` | String | 服务端实际云台标识 |
| `command` | String | 原样回显；无法解析时可为空字符串 |
| `status` | String | `ok`或`error` |
| `code` | Integer | 稳定错误码 |
| `error` | String | 稳定机器可读错误名称 |
| `message` | String | 人类可读诊断，不应用于程序分支 |
| `server_time_ms` | Integer | 服务端Unix UTC毫秒 |
| `data` | Object | 命令结果，错误时通常为空Object |

如果 JSON 或通用封装损坏到无法取得关联字段，但服务端仍决定发送诊断应答，则使用空关联字段和`sequence=0`：

```json
{
  "protocol":"uesim.gimbal",
  "version":"1.1",
  "type":"response",
  "request_id":"",
  "client_id":"",
  "session_id":"",
  "sequence":0,
  "gimbal_id":"camera_gimbal",
  "command":"",
  "status":"error",
  "code":1000,
  "error":"INVALID_JSON",
  "message":"request is not a valid UTF-8 JSON object",
  "server_time_ms":1786387200012,
  "data":{}
}
```

此类应答无法可靠关联到请求，仅用于日志诊断。服务端可以因限流、数据报过大或安全策略直接丢弃，不保证对不可解析请求应答。

## 7. 命令总表

| 命令 | 作用 | 是否改变状态 | 建议应答 |
| --- | --- | --- | --- |
| `ping` | 连通性检查 | 否 | 必须 |
| `get_capabilities` | 查询能力、限位和配置 | 否 | 必须 |
| `set_speed_mode` | 切换粗调/微调/自定义模式 | 是 | 是 |
| `set_custom_speed` | 配置自定义速度和加减速度 | 是 | 是 |
| `set_velocity` | 直接设置两轴角速度 | 是 | 高频时可关闭 |
| `set_direction` | 按归一化方向量控制 | 是 | 高频时可关闭 |
| `step` | 固定角度点动 | 是 | 是 |
| `set_angle` | 设置绝对角度目标 | 是 | 是 |
| `stop_motion` | 停止一个轴或全部轴 | 是 | 是 |
| `set_stabilization` | 配置防抖 | 是 | 是 |
| `release_control` | 停止运动并释放控制者租约 | 是 | 是 |

### 7.1 单控制者租约

协议允许多个客户端执行`ping`和`get_capabilities`，但同一时刻只允许一个客户端修改云台状态。状态发布不取得也不刷新控制者租约。

- 第一个被接受的状态修改命令自动获得控制者租约。
- 控制者由`client_id + session_id`唯一标识。
- 默认租约时间为`1.0 秒`，使用服务端单调实时时钟计时，不受仿真暂停影响。
- 控制者每个被接受的状态修改命令都会刷新租约。
- 其他客户端在租约有效时发送状态修改命令，返回`BUSY`，禁止改变状态。
- `ping`和`get_capabilities`不获取也不刷新租约。
- 租约超时后，下一台发送有效状态修改命令的客户端可以获得租约。
- `release_control`可以由当前控制者立即释放租约。
- `StopGimbal`会清除控制者租约。
- 本地蓝图手动控制优先于 UDP；本地手动控制期间，UDP 状态修改命令返回`BUSY`，`ping`、`get_capabilities`及主动状态发布仍可使用。

本地控制覆盖期按以下规则结束：

- 本地速度/方向控制：调用`StopGimbalMotion`，或本地速度指令超时并完成制动后结束。
- 本地点动/绝对角度控制：到达目标、被本地停止或被新的本地命令取消后结束。
- 生命周期`StopGimbal`：立即结束本地覆盖并清除UDP租约。

本地覆盖不会刷新 UDP 租约。覆盖结束时，若原租约的单调时间尚未到期，原 UDP 控制者仍可继续使用剩余租期；若已到期，下一条有效 UDP 状态修改命令重新竞争租约。其他 UDP 客户端不应依赖本地操作提前释放原租约。

该租约不是身份认证，只用于防止多个合法控制端相互覆盖。

## 8. 命令定义

### 8.1 ping

用于检查服务是否可达，不改变云台状态。

请求：

```json
{
  "protocol":"uesim.gimbal",
  "version":"1.1",
  "type":"request",
  "request_id":"req-1",
  "client_id":"client-a",
  "session_id":"session-a",
  "sequence":1,
  "gimbal_id":"*",
  "command":"ping",
  "params":{}
}
```

成功应答`data`：

```json
{
  "running": true,
  "udp_port": 8870,
  "uptime_ms": 12345
}
```

### 8.2 get_capabilities

查询协议能力和服务器实际限制，不改变云台状态。

请求`params`必须为空Object。

成功应答`data`：

```json
{
  "protocol_version": "1.1",
  "yaw_continuous": true,
  "yaw_output_min_deg": 0.0,
  "yaw_output_max_exclusive_deg": 360.0,
  "pitch_min_deg": -60.0,
  "pitch_max_deg": 60.0,
  "velocity_command_validity_s": 0.1,
  "fine": {
    "yaw_speed_dps": 10.0,
    "pitch_speed_dps": 8.0,
    "step_deg": 1.0
  },
  "coarse": {
    "yaw_speed_dps": 90.0,
    "pitch_speed_dps": 60.0,
    "step_deg": 5.0
  },
  "hard_limits": {
    "max_yaw_speed_dps": 180.0,
    "max_pitch_speed_dps": 120.0,
    "max_step_deg": 10.0
  },
    "commands": [
    "ping",
    "get_capabilities",
    "set_speed_mode",
    "set_custom_speed",
    "set_velocity",
    "set_direction",
    "step",
    "set_angle",
    "stop_motion",
    "set_stabilization",
    "release_control"
  ]
}
```

能力应答中的数值必须来自当前运行实例，不允许发送与实际配置不一致的固定模板。

### 8.3 主动状态发布

状态不是控制请求的应答。云台服务启动后立即发布第一帧，之后默认每`0.1秒`发布一帧（`10Hz`）。不补发暂停期间错过的帧；实际发布上限受游戏线程 Tick 频率约束。状态消息不包含`request_id`、`client_id`、`session_id`、`command`、`status`、`code`或`error`。

状态监听客户端必须：

1. 在云台启动前创建 UDP/IPv4 Socket，并绑定客户端本地`0.0.0.0:8871`；只允许本机程序时可绑定`127.0.0.1:8871`。
2. 只调用`recvfrom`接收，不发送任何状态查询。
3. 校验`protocol="uesim.gimbal"`、`version="1.1"`、`type="state"`和目标`gimbal_id`。
4. 按`sequence`识别丢帧或倒序；服务每次启动时序号从1重新开始。
5. 结束监听时直接关闭客户端 Socket，不需要释放控制租约。

项目参考脚本：

```bash
python3 Tools/gimbal_udp_client.py \
  --local-port 8871 \
  --gimbal-id camera_gimbal \
  listen-state
```

若 UDP `8871`已被其他进程占用，绑定必须失败并报告错误，禁止静默改用随机端口。需要其他端口时，必须在 PTZ Spawn 前同时修改配置的`state_port`及监听程序端口。

完整状态消息：

```json
{
  "protocol": "uesim.gimbal",
  "version": "1.1",
  "type": "state",
  "gimbal_id": "camera_gimbal",
  "sequence": 18,
  "server_time_ms": 1786387200012,
  "data": {
    "running": true,
    "udp": {
      "bind_address": "127.0.0.1",
      "control_port": 8870,
      "state_target_address": "127.0.0.1",
      "state_port": 8871,
      "state_publish_rate_hz": 10.0
    },
    "speed_mode": "fine",
    "control": {
      "yaw_mode": "hold",
      "pitch_mode": "hold",
      "yaw_command_remaining_s": 0.0,
      "pitch_command_remaining_s": 0.0
    },
    "current": {
      "yaw_deg": 15.25,
      "pitch_deg": -2.5,
      "yaw_rate_dps": 0.0,
      "pitch_rate_dps": 0.0
    },
    "target": {"yaw_deg": 15.25, "pitch_deg": -2.5},
    "limits": {"pitch_limit_reached": false},
    "stabilization": {
      "enabled": false,
      "mode": "off",
      "yaw_offset_deg": 0.0,
      "pitch_offset_deg": 0.0,
      "saturated": false
    },
    "last_applied_command": {
      "client_id": "client-a",
      "session_id": "session-a",
      "sequence": 10,
      "server_time_ms": 1786387200012
    },
    "control_owner": {
      "source": "udp",
      "client_id": "client-a",
      "session_id": "session-a",
      "lease_remaining_s": 0.82
    },
    "simulation_time_s": 125.5,
    "dropped_datagrams": 0
  }
}
```

Yaw 始终为`[0,360)`；Pitch 始终为`[-60,+60]`。没有控制者时`control_owner.source`为`none`；本地蓝图正在手动控制时为`local`。

#### 8.3.1 跨机器监听

在 Spawn 时将`Gimbal State Target Address`设置为状态客户端 IPv4；也可以先从状态客户端向 UeSim 控制端口发送任一合法 v1.1 控制协议包，UeSim 会把状态目标地址切换到该包的源 IP。状态端口仍固定为 Spawn 的`state_port`。UeSim 的`Gimbal Bind Address`须设置为`0.0.0.0`或服务器网卡 IPv4，并放行服务器入站 UDP `8870`和客户端入站 UDP `8871`。每个云台只维护一个状态目标，后到的合法远程客户端会接管状态目标地址。

### 8.4 set_speed_mode

请求参数：

| 字段 | 类型 | 必填 | 允许值 |
| --- | --- | --- | --- |
| `mode` | String | 是 | `fine`、`coarse`、`custom` |

示例：

```json
{
  "mode": "fine"
}
```

切换模式不改变当前角度。正在执行`set_direction`控制时，新模式在下一条`set_direction`到达时生效；直接`set_velocity`不使用速度模式缩放。

成功应答`data`：

```json
{
  "applied_mode": "fine",
  "yaw_speed_dps": 10.0,
  "pitch_speed_dps": 8.0,
  "step_deg": 1.0
}
```

### 8.5 set_custom_speed

配置并切换到 Custom 模式。

参数：

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `yaw_speed_dps` | Number | 是 | `>0`且不超过能力上限 |
| `pitch_speed_dps` | Number | 是 | `>0`且不超过能力上限 |
| `yaw_acceleration_dps2` | Number | 是 | `>0`且不超过能力上限 |
| `pitch_acceleration_dps2` | Number | 是 | `>0`且不超过能力上限 |
| `brake_deceleration_dps2` | Number | 是 | `>0`且不超过能力上限 |
| `step_deg` | Number | 是 | `0.1～10.0` |

示例：

```json
{
  "yaw_speed_dps": 30.0,
  "pitch_speed_dps": 20.0,
  "yaw_acceleration_dps2": 120.0,
  "pitch_acceleration_dps2": 90.0,
  "brake_deceleration_dps2": 480.0,
  "step_deg": 0.5
}
```

请求必须作为一个事务校验：任意字段无效时全部拒绝，禁止只应用部分字段。

### 8.6 set_velocity

直接设置两轴带符号角速度。

参数：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `yaw_rate_dps` | Number | 是 | 正值向右，负值向左 |
| `pitch_rate_dps` | Number | 是 | 正值向上，负值向下 |

示例：

```json
{
  "yaw_rate_dps": 30.0,
  "pitch_rate_dps": -5.0
}
```

规则：

- 两个字段都必须提供。
- 速度绝对值不能超过`get_capabilities`返回的硬限制。
- 请求被 Game Thread 接受时，同时刷新 Yaw 和 Pitch 的`0.1 秒`有效期。
- 有效期从服务端接受时间开始，不使用`client_time_ms`计算。
- 重复数据报不重新执行，也不刷新有效期。
- 新序列号的数据报覆盖旧目标速度，不做速度叠加。
- 零速度使对应轴进入主动制动。
- 超时后两轴进入主动制动并保持停止位置。

成功应答`data`：

```json
{
  "accepted_yaw_rate_dps": 30.0,
  "accepted_pitch_rate_dps": -5.0,
  "valid_until_simulation_time_s": 125.6
}
```

推荐发送频率为`20～100 Hz`。低于`10 Hz`无法在固定`0.1 秒`有效期下保持连续速度。

### 8.7 set_direction

使用归一化输入控制方向，速度由当前 Fine、Coarse 或 Custom 模式决定。

参数：

| 字段 | 类型 | 必填 | 范围 |
| --- | --- | --- | --- |
| `yaw_input` | Number | 是 | `[-1,1]` |
| `pitch_input` | Number | 是 | `[-1,1]` |

方向：

```text
yaw_input   -1=左，0=停止Yaw，+1=右
pitch_input -1=下，0=停止Pitch，+1=上
```

示例：

```json
{
  "yaw_input": 1.0,
  "pitch_input": 0.25
}
```

应用速度：

```text
YawRate   = yaw_input * CurrentModeYawSpeed
PitchRate = pitch_input * CurrentModePitchSpeed
```

有效期、重复包和超时行为与`set_velocity`完全一致。两个输入都为零时等价于`stop_motion`的`axis=all`。

### 8.8 step

执行固定角度增量，使用位置控制器到达目标。

参数：

| 字段 | 类型 | 必填 | 范围 |
| --- | --- | --- | --- |
| `yaw_delta_deg` | Number | 是 | `[-10,10]` |
| `pitch_delta_deg` | Number | 是 | `[-10,10]` |

两个值禁止同时为零。

示例：

```json
{
  "yaw_delta_deg": 1.0,
  "pitch_delta_deg": 0.0
}
```

规则：

- 增量以命令被接受时的当前锁存目标为基准。
- Yaw 可以跨越 0/360 边界。
- Pitch 结果钳制到`[-60,+60]`。
- 点动目标锁存，不使用`0.1 秒`速度 watchdog。
- 重复请求必须由幂等机制拦截，禁止重复增加目标角度。

成功应答`data`：

```json
{
  "target_yaw_deg": 16.25,
  "target_pitch_deg": -2.5,
  "pitch_clamped": false
}
```

### 8.9 set_angle

设置绝对角度目标。

参数：

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `yaw_deg` | Number | 是 | 任意有限角度，服务端归一化到`[0,360)` |
| `pitch_deg` | Number | 是 | 默认必须位于`[-60,+60]` |
| `yaw_travel` | String | 是 | `shortest`、`clockwise`、`counterclockwise` |
| `allow_clamp` | Boolean | 否 | 默认`false` |

示例：

```json
{
  "yaw_deg": 350.0,
  "pitch_deg": 20.0,
  "yaw_travel": "shortest",
  "allow_clamp": false
}
```

规则：

- `allow_clamp=false`且 Pitch 越界：返回`OUT_OF_RANGE`，不改变任何轴。
- `allow_clamp=true`且 Pitch 越界：钳制到最近边界，并在应答中返回`pitch_clamped=true`。
- 该命令取消两轴速度控制并切换为位置模式。
- 目标锁存，不需要按`0.1 秒`重复发送。
- `shortest`在正负方向距离相同的`180°`情况下选择正方向。

成功应答`data`：

```json
{
  "target_yaw_deg": 350.0,
  "target_pitch_deg": 20.0,
  "yaw_travel": "shortest",
  "pitch_clamped": false
}
```

### 8.10 stop_motion

停止运动但保持 UDP 服务运行。

参数：

| 字段 | 类型 | 必填 | 允许值 |
| --- | --- | --- | --- |
| `axis` | String | 是 | `yaw`、`pitch`、`all` |

示例：

```json
{
  "axis": "all"
}
```

规则：

- 取消指定轴的速度和位置目标。
- 使用主动制动减速度停止。
- 停止后保持实际停止角度。
- `stop_motion`不关闭 UDP Socket。
- `axis=yaw`不能清除 Pitch 控制；`axis=pitch`同理。

### 8.11 set_stabilization

配置防抖。

参数：

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `enabled` | Boolean | 是 | 是否启用 |
| `mode` | String | 是 | `off`、`follow_damping`、`world_lock` |
| `gain` | Number | 否 | `[0,1]` |
| `response_hz` | Number | 否 | `>0`且不超过能力上限 |
| `max_offset_deg` | Number | 否 | `>=0`且不超过能力上限 |
| `max_rate_dps` | Number | 否 | `>=0`且不超过能力上限 |

示例：

```json
{
  "enabled": true,
  "mode": "follow_damping",
  "gain": 0.9,
  "response_hz": 20.0,
  "max_offset_deg": 5.0,
  "max_rate_dps": 180.0
}
```

规则：

- `enabled=false`时`mode`必须为`off`。
- `enabled=true`时`mode`禁止为`off`。
- 省略的可选数值保持当前配置，不恢复默认值。
- 所有参数先完成校验，再作为一个事务应用。
- 首次启用或切换模式时以当前姿态重置滤波器，禁止产生角度跳变。

### 8.12 release_control

当前 UDP 控制者主动结束控制。

请求`params`必须为空Object：

```json
{}
```

规则：

- 只有当前`client_id + session_id`控制者可以成功执行。
- 命令先对两轴执行等价于`stop_motion axis=all`的主动制动，再释放租约。
- 非当前控制者请求返回`BUSY`。
- 租约释放后，后续状态修改命令可以由任意客户端重新获得租约。
- 该命令不关闭 UDP 服务。

成功应答`data`：

```json
{
  "released": true
}
```

## 9. 错误码

错误码和错误名称是稳定协议字段。客户端应依据`code`或`error`处理，禁止解析`message`文本。

| Code | Error | 含义 |
| ---: | --- | --- |
| `0` | `OK` | 成功 |
| `1000` | `INVALID_JSON` | 不是合法UTF-8 JSON对象 |
| `1001` | `UNSUPPORTED_PROTOCOL` | `protocol`不受支持 |
| `1002` | `UNSUPPORTED_VERSION` | 协议版本不受支持 |
| `1003` | `INVALID_ENVELOPE` | 通用字段缺失、类型错误或格式错误 |
| `1004` | `UNKNOWN_COMMAND` | 命令不存在 |
| `1005` | `INVALID_PARAMS` | 参数缺失或类型错误 |
| `1006` | `OUT_OF_RANGE` | 数值超出允许范围 |
| `1007` | `GIMBAL_ID_MISMATCH` | 云台标识不匹配 |
| `1008` | `STALE_SEQUENCE` | 序列号旧于已接受序列号 |
| `1009` | `NOT_RUNNING` | 云台服务未运行或正在停止 |
| `1010` | `BUSY` | 当前状态暂时不能执行命令 |
| `1011` | `INTERNAL_ERROR` | 服务端内部错误 |
| `1012` | `RATE_LIMITED` | 客户端发送速率超过限制 |
| `1013` | `PAYLOAD_TOO_LARGE` | 数据报超过4096字节 |
| `1014` | `UNKNOWN_PARAMETER` | `params`包含未知字段 |
| `1015` | `REQUEST_ID_REUSED` | 同一request_id被用于不同内容 |

若数据报过大、源地址无效、服务正在关闭或系统资源不足，服务端可能直接丢弃而无法发送错误应答。

## 10. 顺序、重复和幂等

### 10.1 session和sequence

- 客户端每次进程启动或逻辑重新连接时必须生成新的`session_id`。
- 同一`client_id + session_id`内，`sequence`必须从正整数开始严格递增。
- 服务端按`client_id + session_id`保存最后消费的序列号。
- 新 session 不继承旧 session 的序列号。

“消费”发生在通用封装、标识符、可选字段类型和`params` Object校验通过之后、命令分派之前。因此，即使命令随后返回`GIMBAL_ID_MISMATCH`、`UNKNOWN_COMMAND`、`INVALID_PARAMS`、`OUT_OF_RANGE`或`BUSY`，该 sequence 也已经被消费，客户端下一条新请求必须使用更大的 sequence。通用封装校验失败时 sequence 不被消费。

### 10.2 重复请求

服务端应保存最近请求的幂等缓存，推荐：

```text
缓存时间：10秒
最大条目：每个云台256条
```

收到相同`client_id + session_id + request_id + sequence`且消息内容一致时：

- 不再次执行命令。
- 不刷新速度指令的`0.1 秒`有效期。
- 若原请求要求应答，则逐字节返回缓存的原始应答；其中`server_time_ms`保持第一次处理该请求时的值，用于识别幂等重放而不是新的执行时间。

同一个`request_id`用于不同 sequence 或不同内容时返回`REQUEST_ID_REUSED`。

### 10.3 乱序请求

- sequence 大于最后消费值：正常处理。
- sequence 等于已处理请求且命中幂等缓存：按重复请求处理。
- sequence 小于或等于最后消费值但无法匹配已处理请求：返回`STALE_SEQUENCE`，禁止执行。

客户端若并行发送多个请求，必须接受 UDP 到达顺序可能与发送顺序不同，较低 sequence 的迟到包可能被拒绝。需要严格顺序的离散控制命令应串行发送，并等待应答后再发送下一条。

### 10.4 重试建议

对于`step`、`set_angle`、`set_speed_mode`等离散命令：

- 建议等待应答`200 ms`。
- 未收到应答时最多重试3次。
- 重试必须发送完全相同的`request_id`、`sequence`和消息内容。
- 收到成功或明确错误应答后停止重试。

对于`set_velocity`和`set_direction`：

- 禁止重试旧速度包。
- 应按固定周期发送带新 sequence 的最新控制值。
- 丢失一包时由后续新包恢复。
- 停止控制时应主动发送`stop_motion`，watchdog仅作为失联保护。

## 11. 0.1秒速度指令有效期

### 11.1 计时起点

有效期从命令通过校验并在 Game Thread 被接受时开始：

```text
ValidUntil = CurrentSimulationTime + 0.1s
```

禁止使用客户端时间戳计算有效期，因为客户端和服务端时钟可能不同步。

### 11.2 仿真暂停

watchdog 使用仿真时间：

- 仿真暂停时有效期不递减。
- 固定步长回放中按固定仿真步长递减。
- 时钟 generation 变化或时间回退时，所有速度指令立即失效并进入停止状态。

### 11.3 控制频率

| 频率 | 预期行为 |
| --- | --- |
| `20～100 Hz` | 推荐连续控制范围 |
| `10 Hz` | 临界；调度抖动可能导致短暂停顿 |
| `<10 Hz` | 无法保持连续速度，应使用`set_angle`或`step` |
| `>200 Hz` | 无实际必要，可能触发限流 |

## 12. 接收端处理要求

### 12.1 线程模型

推荐实现：

1. Socket 接收线程只复制数据报字节、源IP、源端口和接收单调时间。
2. 数据放入有界 MPSC 队列。
3. Game Thread 从队列读取、解析 JSON、检查序列号并调用云台控制器。
4. 应答序列化后通过同一 Socket 发回源端点。

Socket 线程禁止直接访问 Actor、Scene Component、UObject 或蓝图事件。

### 12.2 队列和限流

推荐默认值：

```text
最大排队数据报：256
单源最大处理速率：200 packets/s
Socket接收缓冲：2 MiB
单帧最大处理数据报：64
```

队列满时应丢弃队列中最旧的数据报、保留最新数据报，并增加`dropped_datagrams`。这样既能避免内存无界增长，也能降低过期速度命令在卡顿后被继续执行的风险。离散命令必须依靠应答和幂等重试处理丢包；速度控制器应持续发送最新状态，不依赖积压消息追赶。

### 12.3 事务性

每个命令必须先完成完整校验，再修改任何云台状态。一个请求要么全部成功，要么不产生任何状态变化。

## 13. 安全要求

协议 v1.1不提供身份认证、加密、完整性校验或防伪造能力。因此：

- 默认应绑定`127.0.0.1`。
- 跨机器使用时应绑定指定的可信网卡地址，避免无必要地使用`0.0.0.0`。
- 必须通过操作系统防火墙限制允许访问的源地址和 UDP 端口。
- 只能部署在隔离、可信的仿真网络中。
- 禁止直接暴露到互联网。
- 需要跨不可信网络时，应通过 VPN、受控隧道或上层安全网关传输。

UDP 源地址可以被伪造。`client_id`和`session_id`只用于顺序和幂等，不是认证凭据。

## 14. Python参考客户端

v1.0.13 发布包随附可直接运行、仅依赖 Python 标准库的完整客户端 `Tools/gimbal_udp_client.py`。它覆盖本协议全部命令，并自动生成 request/session/时间字段。例如：

需要人工交互测试时，可以使用带 Tkinter 界面的 `gimbal_udp_ui.py`。在 MATRiX 运行包根目录运行 `python3 Tools/gimbal_udp_ui.py`。详细操作和验收步骤见 [Camera_Gimbal_UI_Tool_CN.md](Camera_Gimbal_UI_Tool_CN.md)。

```bash
# 被动监听服务端主动发布的状态（不发送请求）
python3 Tools/gimbal_udp_client.py --local-port 8871 --gimbal-id camera_gimbal listen-state

# 多条状态修改命令必须复用同一 session，并严格增加 sequence
Session=$(python3 -c 'import uuid; print(uuid.uuid4())')

# 粗调模式，以归一化方向控制右转和轻微上转
python3 Tools/gimbal_udp_client.py --port 8870 --gimbal-id camera_gimbal --session-id "$Session" --sequence 1 speed coarse
python3 Tools/gimbal_udp_client.py --port 8870 --gimbal-id camera_gimbal --session-id "$Session" --sequence 2 direction 1.0 0.25

# 微调模式和绝对角度
python3 Tools/gimbal_udp_client.py --port 8870 --gimbal-id camera_gimbal --session-id "$Session" --sequence 3 speed fine
python3 Tools/gimbal_udp_client.py --port 8870 --gimbal-id camera_gimbal --session-id "$Session" --sequence 4 angle 15 -2 --travel shortest

# 停止运动；若还要交给其他 UDP 客户端，再释放控制租约
python3 Tools/gimbal_udp_client.py --port 8870 --gimbal-id camera_gimbal --session-id "$Session" --sequence 5 stop all
python3 Tools/gimbal_udp_client.py --port 8870 --gimbal-id camera_gimbal --session-id "$Session" --sequence 6 release
```

每次单独启动脚本都会生成新的 session，适合单命令联调。连续控制程序必须在同一 socket/session 内保持 sequence 递增；可复用下方最小代码，或导入参考脚本中的封装逻辑。

以下示例只绑定 UDP `8871`，接收并校验一帧主动状态：

```python
import json
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 8871))
sock.settimeout(1.0)

payload, sender = sock.recvfrom(4096)
message = json.loads(payload.decode("utf-8"))
if (message.get("protocol"), message.get("version"), message.get("type")) != (
    "uesim.gimbal", "1.1", "state"
):
    raise RuntimeError(f"invalid gimbal state message from {sender}")
if message.get("gimbal_id") != "camera_gimbal":
    raise RuntimeError("unexpected gimbal_id")

print(message["data"])
```

连续速度发送端必须为每个新包增加 sequence，并发送当前最新速度。退出控制前发送一次`stop_motion`。

### 14.1 本机最小联调步骤

1. 确认传感器配置只包含`control_port=8870`、`state_port=8871`、`stablization`，且`sensor_type="ptzrgb"`。
2. 先启动状态监听，避免错过服务启动后的首帧：

   ```bash
   python3 Tools/gimbal_udp_client.py --local-port 8871 --gimbal-id camera_gimbal listen-state
   ```

3. 启动 UeSim 仿真并生成 PTZRGB；若需要图像，同时确认相机 Sensor 已启动。
4. 另开终端检查控制端口：

   ```bash
   python3 Tools/gimbal_udp_client.py --port 8870 --gimbal-id camera_gimbal ping
   ```

5. 状态终端应持续收到`version="1.1"`、`type="state"`消息，`data.udp.control_port=8870`、`data.udp.state_port=8871`、`data.udp.state_publish_rate_hz=10`。
6. 使用图形测试工具验证上下左右控制和角度显示：

   ```bash
   python3 Tools/gimbal_udp_ui.py --port 8870 --state-port 8871 --gimbal-id camera_gimbal
   ```

同一个 UDP `8871`端口同一时刻通常只能由一个监听进程绑定。启动 UI 前应关闭命令行`listen-state`，否则 UI 必须报告端口占用，不能静默改用随机端口。

### 14.2 跨机器最小联调步骤

1. UeSim端将`BindAddress`设置为服务器网卡IPv4或`0.0.0.0`，不要保持`127.0.0.1`。
2. 状态客户端先绑定本机 UDP `state_port`。
3. 将 UeSim Spawn 参数`StateTargetAddress`设置为状态客户端IPv4；或者从状态客户端向 UeSim 控制端口发送合法 v1.1 `ping`，使服务自动学习该客户端IP。
4. 放行 UeSim服务器入站 UDP `control_port`，以及状态客户端入站 UDP `state_port`。
5. 使用抓包或状态消息中的`data.udp.state_target_address`确认目标地址正确。

## 15. 部署检查表

对外交付联调前必须确认：

1. UeSim 和外部控制器使用协议版本`1.1`；v1.0客户端不兼容。
2. PTZ配置只持久化`control_port`、`state_port`和`stablization`，未写入内部 Spawn 字段。
3. 外部控制器的目标IP、端口和 UeSim StartGimbal 参数一致。
4. `gimbal_id`与 UeSim Actor一致；未修改蓝图默认值时使用`camera_gimbal`。
5. 同一云台的控制端口与状态端口不同；同一主机上的各云台控制端口不冲突。
6. 防火墙允许 UeSim 入站控制端口及状态客户端入站`state_port`。
7. 控制消息是单个 UTF-8 JSON Object，且不超过4096字节。
8. client_id稳定，session_id每次客户端启动时更新。
9. sequence在session内严格递增。
10. 离散命令重试时复用原request_id和sequence。
11. 连续速度以20～100 Hz发送，并在结束时发送release_control；只暂时停车时发送stop_motion。
12. 客户端正确处理UDP丢包、超时、重复应答和乱序应答。
13. 客户端不依赖message文本进行程序判断。
14. 状态客户端先绑定 Spawn 配置的`state_port`，只接收`type="state"`，不发送状态查询。
15. RGB图像采集和云台服务分别启动，不能用一个生命周期代替另一个。
16. 跨机器网络为可信隔离网络，未将端口暴露到公网。

## 16. 版本兼容和扩展

- v1.x新增可选顶层字段时，旧实现可以忽略。
- 新增命令参数必须通过新协议版本或明确的扩展Object引入；v1.1对未知params字段返回错误。
- 改变现有字段含义、单位、范围、默认值或命令副作用时，必须升级主版本。
- 服务端收到不支持的版本必须返回`UNSUPPORTED_VERSION`，禁止尝试猜测解析。
- 客户端应先调用`get_capabilities`确认实例的实际能力，不应只依赖本地默认值。

## 17. 协议一致性摘要

| 项目 | v1.1规定 |
| --- | --- |
| Yaw单位 | 度 |
| Yaw查询范围 | `[0,360)` |
| Pitch单位 | 度 |
| Pitch范围 | `[-60,+60]` |
| 角速度单位 | 度/秒 |
| 角加速度单位 | 度/秒² |
| 速度指令有效期 | 固定`0.1秒` |
| 推荐速度发送频率 | `20～100 Hz` |
| 状态发布方式 | 服务端主动 UDP 单播，无查询命令 |
| 默认状态发布频率 | `10 Hz` |
| 默认状态目标端口 | UDP `8871`，由 PTZ Spawn 配置 |
| Fine默认速度 | Yaw`10°/s`，Pitch`8°/s` |
| Coarse默认速度 | Yaw`90°/s`，Pitch`60°/s` |
| Fine默认点动 | `1°` |
| Coarse默认点动 | `5°` |
| JSON编码 | UTF-8，无BOM |
| 最大数据报 | `4096字节` |
| 认证和加密 | 不支持，仅可信网络 |
