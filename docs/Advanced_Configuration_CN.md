# 高级配置指南

[← 返回项目首页](../README.md) · [中文文档索引](README_CN.md)

本文依据 MATRiX v1.0.13 Linux 运行包的实际 `config.json` 和对应源码校正。普通用户优先通过界面修改配置；手动编辑适合自动化、批量修改和故障排查。

## 配置文件位置

发布包路径为：

~~~text
UeSim/Content/model/config/config.json
UeSim/Content/model/config/sensors/*.json
~~~

启动器读取和保存的是 `config.json`。`sensors/*.json` 是可复用模板，不会仅因修改模板而自动改变当前机器人配置。

## 当前 robot 配置结构

下面的字段与当前 C++ 配置结构一致：

~~~json
{
  "robot": {
    "mujoco_model": "model/xgb/xgb.xml",
    "main_body": "base_link",
    "weapon": "",
    "network_mode": "standalone",
    "sensor_sync_mode": false,
    "inside_mc": true,
    "zenoh_router": "tcp/0.0.0.0:7447",
    "position": { "x": 0, "y": 0, "z": 1 },
    "state_port": "mujoco/state",
    "cmd_port": "mujoco/cmd",
    "mujoco_running": false,
    "sensors": {}
  }
}
~~~

> `mujoco_model` 相对于 `UeSim/Content` 解析。使用 `model/xgb/xgb.xml` 这类相对路径，不要写开发机绝对路径。

## robot 字段

| 字段 | 类型 | 当前含义 |
|---|---|---|
| `mujoco_model` | string | 要加载的 MJCF/XML 路径 |
| `main_body` | string | 传感器默认挂载和机身参考 body，通常为 `base_link` |
| `weapon` | string | 可选武器/任务配置字段 |
| `network_mode` | string | `standalone`、`server` 或 `client`；控制 LanSync 联网，不等同于 Zenoh 会话模式 |
| `sensor_sync_mode` | boolean | 机器人级传感器同步开关，会派生到该机器人所有传感器 |
| `inside_mc` | boolean | 选择 UE 内置运动控制链路 |
| `zenoh_router` | string | 运动控制与仿真共享的 Zenoh 端点 |
| `position` | object | 机器人初始位置 |
| `state_port` | string | 机器人状态 Zenoh key；当前默认 `mujoco/state` |
| `cmd_port` | string | 机器人命令 Zenoh key；当前默认 `mujoco/cmd` |
| `mujoco_running` | boolean | 由启动器/Spawn 流程消费的运行状态字段，不是 UDP 端口开关 |
| `sensors` | object | 动态传感器对象；键名必须唯一 |

`state_port` 和 `cmd_port` 为兼容旧配置保留了“port”名称，但当前类型是字符串消息 key。旧数字值仍能读取，保存后会写为字符串；不要再把 `25001` / `25002` 当作当前默认控制端口。

## 已移除或不应继续写入的旧字段

以下字段不属于当前 `FMujocoRobotConfig`，保存配置时会被删除或忽略：

- `EgoView`
- `synchronous_mode`
- `synchronous_frequency`
- `sensor_master_rate_hz`
- `sensor_overrun_policy`
- `require_realtime_sensor_frequency`
- `sensor_synchronization`
- `gameserver` / `enablegameserver`

当前 JSON 只通过机器人级 `sensor_sync_mode` 选择同步/异步传感器时序。主频和过载策略使用运行时安全默认值，不再作为项目 JSON 字段暴露。

## 动态传感器对象

`robot.sensors` 不是固定的 `camera/depth_sensor/lidar` 三项。可添加任意数量的传感器，只需每个对象键名唯一：

~~~json
{
  "robot": {
    "sensors": {
      "camera": {
        "sensor_type": "rgb",
        "topic": "/front_camera/image/compressed",
        "frequency": 10,
        "sensor_attach": "base_link"
      },
      "camera_1": {
        "sensor_type": "rgb",
        "topic": "/rear_camera/image/compressed",
        "frequency": 10,
        "sensor_attach": "base_link"
      }
    }
  }
}
~~~

配置库保存时以 `Sensors` 数组为最终依据：空数组会写成空对象；同名传感器后写入者会覆盖前者。传感器完整字段见[传感器配置教程](Sensor_Config_Tutorial.md)。

## 联网模式与 Zenoh 的区别

`network_mode` 用于 LanSync：

- `standalone`：不自动创建 LanSync 服务。
- `server`：以服务端模式创建 LanSync。
- `client`：以客户端模式创建 LanSync。

Zenoh 传感器和运动控制连接由 `zenoh_router` 及对应 Zenoh Subsystem 配置管理。不要用 `network_mode` 判断是否发布传感器。

## GameUserSettings.ini

Unreal 画质配置位于：

~~~text
UeSim/Saved/Config/Linux/GameUserSettings.ini
~~~

常见 Scalability 字段：

~~~ini
[ScalabilityGroups]
sg.ResolutionQuality=100
sg.TextureQuality=3
sg.ShadowQuality=3
sg.PostProcessQuality=3
~~~

这些字段影响渲染负载，但不会修改 MuJoCo worker 或传感器目标频率。相机、全景/鱼眼和 LiDAR 负载过高时，应同时降低传感器分辨率、采样量或发布频率。
