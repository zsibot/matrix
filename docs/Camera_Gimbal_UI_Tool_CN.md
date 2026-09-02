# 云台四方向图形测试工具

> 适用于 MATRiX v1.0.13 Linux 运行包。

## 启动

先在 Unreal 蓝图中启动云台：

```text
StartGimbal
    UdpListenPort       = 8870
    StatePublishPort    = 8871
    BindAddress         = 127.0.0.1
    StateTargetAddress  = 127.0.0.1
    StatePublishRateHz  = 10
```

在 MATRiX v1.0.13 运行包根目录执行：

```bash
python3 Tools/gimbal_udp_ui.py
```

工具默认连接：

```text
127.0.0.1:8870
Gimbal ID = camera_gimbal
控制频率 = 20 Hz
云台状态接收端口 = 8871
任务 NPC 状态接收端口 = 8872
```

需要覆盖参数时使用：

```bash
python3 Tools/gimbal_udp_ui.py \
  --host 127.0.0.1 \
  --port 8870 \
  --state-bind-address 0.0.0.0 \
  --state-port 8871 \
  --npc-state-port 8872 \
  --gimbal-id camera_gimbal \
  --frequency 20 \
  --speed-scale 1.0 \
  --speed-mode fine
```

## 操作

界面的操作区包含“细调/粗调”模式选择，以及“上、下、左、右”四个方向按钮。启动默认使用细调模式；可通过`--speed-mode coarse`改为默认粗调。云台状态区显示：

- 状态源地址、发布序号和接收/超时状态。
- 当前 Yaw、Pitch。
- 当前 Yaw/Pitch 角速度。
- 服务端确认的当前细调、粗调或自定义速度模式。
- 防抖开关和模式。

“任务 NPC 状态（UDP 8872）”区域监听服务端主动发布的 NPC 状态，并显示：

- 最新报文的来源 IP、来源端口和 UDP 报文大小。
- 最新报文的完整 JSON 内容，包含中文和嵌套字段；字段顺序不影响显示。
- 最后一条报文距当前的时间，便于判断发布是否中断。
- 非 UTF-8 JSON 报文的格式错误和可读原文，便于联调定位。

工具不限定 NPC 状态的 JSON 字段结构，因此 NPC 发布端新增字段时不需要修改 UI。UDP 单包过大时，界面最多显示前 16000 个字符，但接收链路仍会接收完整报文。

NPC 状态区会占用窗口的主要可伸缩空间，支持横向和纵向滚动。拖动窗口边缘可以继续扩大显示区域；即使状态以`10 Hz`持续刷新，UI也会保持当前滚动位置，不会自动跳回 JSON 顶部。

当前场景实测的任务 NPC 状态格式如下，`rotation`为四元数，`translation`和`scale3D`均使用`x/y/z`分量：

```json
{
  "rotation": { "x": 0, "y": 0, "z": 0, "w": 1 },
  "translation": { "x": -2380, "y": 1420, "z": 0 },
  "scale3D": { "x": 1, "y": 1, "z": 1 }
}
```

数值仅为报文示例，UI不会把它们作为默认值。

UI只绑定状态端口接收服务端主动发布的`type="state"`消息，不发送状态查询。启动时会发送一次`ping`，用于让跨机器的 UeSim 获知状态客户端 IP；这不会取得控制租约。

`--state-bind-address`同时用于云台状态端口`8871`和任务 NPC 状态端口`8872`。两个端口必须不同；如果任一端口已被其他程序占用，工具会给出明确错误并退出。

按钮操作：

- 细调：发送`set_speed_mode {"mode":"fine"}`，后续方向控制使用较低速度。
- 粗调：发送`set_speed_mode {"mode":"coarse"}`，后续方向控制使用较高速度。
- 按住按钮：以固定频率持续发送方向控制，刷新`0.1秒`有效期。
- 松开按钮：立即发送`stop_motion`。
- 关闭窗口：停止运动、释放UDP控制租约并关闭Socket。

模式切换不会改变当前角度；如果切换时仍按住方向按钮，模式命令会先于下一条方向包发送，云台再按照自身加速度限制平滑切换速度。界面在收到主动状态消息后显示“当前模式”作为服务端确认。

按钮方向约定：

| 按钮 | 控制值 |
| --- | --- |
| 左 | `yaw_input=-1` |
| 右 | `yaw_input=+1` |
| 上 | `pitch_input=+1` |
| 下 | `pitch_input=-1` |

UDP服务必须先由蓝图`StartGimbal`启动；本工具不能远程启动或关闭云台服务。完整协议见[Camera_Gimbal_UDP_JSON_Protocol_CN.md](Camera_Gimbal_UDP_JSON_Protocol_CN.md)。
