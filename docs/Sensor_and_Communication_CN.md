# 传感器与 Zenoh 通信指南

[← 返回项目首页](../README.md) · [中文文档索引](README_CN.md)

本文依据当前 `RobotSensorSimulation`、`MujocoSceneImporter` 和 `MyProjectRobotZenohPlugin` 源码校正，说明传感器类型、默认频率、数据格式、时间戳和 Zenoh key 约定。完整 JSON 示例见[传感器配置教程](Sensor_Config_Tutorial.md)。

## 配置位置

~~~text
Content/model/config/config.json
Content/model/config/sensors/
├── config_default.json
├── config_fisheyecamera.json
├── config_infrared.json
├── config_lidar.json
├── config_panorama.json
├── config_ptzrgb.json
├── mid360_slam.json
└── config_zg.json
~~~

v1.0.13 Linux 运行包位于 `UeSim/Content/model/config/`。

## 当前传感器类型

| `sensor_type` | 传感器 | 典型默认频率 | 主要输出 |
|---|---|---:|---|
| `imu` | IMU | 500 Hz | ROS 2 IMU CDR |
| `odom` | 里程计 | 100 Hz | ROS 2 Odometry CDR |
| `gps` | GPS | 100 Hz | GPS/定位数据 |
| `rgb` | RGB 相机 | 10 Hz | `sensor_msgs/msg/CompressedImage` |
| `infrared` | 红外/热成像相机 | 10 Hz | 压缩图像 |
| `depth` | 深度相机 | 10 Hz | PNG 无损深度图；可选 float32 原始深度 |
| `fisheye` | 181°–360° 鱼眼相机 | 10 Hz | 压缩图像 |
| `panoramargb` | 360×180 全景 RGB | 10 Hz | 压缩图像 |
| `mid360` | Livox Mid360 模拟 | 10 Hz | `sensor_msgs/msg/PointCloud2` |
| `airy` | Airy/RoboSense 模拟 | 10 Hz | `sensor_msgs/msg/PointCloud2` |
| 通用 LiDAR Actor | 可配置线数/FOV 的通用 LiDAR | 按 Actor 配置 | `sensor_msgs/msg/PointCloud2` |

旧 `wargb` / `wadepth` 广角类型已由 `fisheye` 替代。当前源码模板没有 `panoramadepth`；需要全景深度时应先确认目标运行包是否另有实现，不要直接复制旧配置。

## 通用字段

| 字段 | 说明 |
|---|---|
| `sensor_type` | 传感器运行时类型 |
| `topic` | ROS 风格话题名；运行时 Zenoh key 通常采用 `rt/<topic>` 约定 |
| `frequency` | 目标采样/发布频率（Hz） |
| `position` | 相对 `sensor_attach` body 的位置，单位米 |
| `rotation` | Roll/Pitch/Yaw，单位度 |
| `sensor_attach` | MuJoCo body 名，通常为 `base_link` |
| `width` / `height` | 图像分辨率 |
| `fov` | 水平视场角 |
| `frame_id` / `child_frame_id` | ROS 2 Header/TF 相关 frame 标识 |
| `cloudmode` | 深度相关兼容字段 |
| `draw_points` / `random_scan` | LiDAR 可视化/扫描选项 |
| `simulate_motion_distortion` | Airy 扫描运动畸变模型 |
| `CubeFaceSize` | 全景/鱼眼内部六面采样分辨率 |
| `K1`–`K4` | Kannala–Brandt 鱼眼径向畸变系数 |

## 配置示例

### RGB

~~~json
"camera": {
  "sensor_type": "rgb",
  "topic": "/front_camera/image/compressed",
  "frequency": 10,
  "position": { "x": 0.18, "y": 0, "z": 0.3 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "height": 1080,
  "width": 1920,
  "fov": 120,
  "sensor_attach": "base_link"
}
~~~

### 深度

~~~json
"depth_sensor": {
  "sensor_type": "depth",
  "topic": "/front_depth/image/compressed",
  "frequency": 10,
  "position": { "x": 0.18, "y": 0, "z": 0.3 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "height": 480,
  "width": 640,
  "fov": 120,
  "cloudmode": false,
  "sensor_attach": "base_link"
}
~~~

深度 PNG 使用 R/G 通道编码米值：`depth_m = R + G / 255.0`，无效深度为全零。独立 Robot Sensor Actor 还可发布以 `MDEP` 开头的 float32 原始深度 payload。

### 鱼眼

~~~json
"fisheye": {
  "sensor_type": "fisheye",
  "topic": "/fisheye/front_left/compressed",
  "frequency": 10,
  "position": { "x": 0.27, "y": 0, "z": 0.5 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "height": 1080,
  "width": 1920,
  "fov": 210,
  "CubeFaceSize": 512,
  "K1": 0,
  "K2": 0,
  "K3": 0,
  "K4": 0,
  "sensor_attach": "base_link"
}
~~~

### 全景 RGB

~~~json
"panoramargb": {
  "sensor_type": "panoramargb",
  "topic": "/panoramargb/front_camera/compressed",
  "frequency": 10,
  "position": { "x": 0, "y": 0, "z": 0.3 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "height": 1080,
  "width": 1920,
  "CubeFaceSize": 512,
  "sensor_attach": "base_link"
}
~~~

### Mid360 与 Airy

~~~json
"front_lidar": {
  "sensor_type": "mid360",
  "topic": "/front_lidar",
  "frequency": 10,
  "position": { "x": 0.2, "y": 0, "z": 0.1 },
  "rotation": { "roll": 0, "pitch": 0, "yaw": 0 },
  "draw_points": false,
  "random_scan": false,
  "sensor_attach": "base_link"
}
~~~

将 `sensor_type` 改为 `airy` 可使用 Airy 模板，并可增加 `simulate_motion_distortion`。

## Zenoh key 与端点

传感器桥接约定为：

~~~text
JSON topic: /front_camera/image/compressed
Zenoh key:  rt/front_camera/image/compressed
~~~

机器人控制 key 不加 `rt/`：

~~~text
mujoco/state
mujoco/cmd
~~~

`state_port` / `cmd_port` 是历史字段名，当前保存的是字符串 key，不是 `25001` / `25002` UDP 端口。

常见端点：

- 监听地址：`tcp/0.0.0.0:7447`。
- 本机客户端连接：`tcp/127.0.0.1:7447`。
- 跨机器客户端连接：`tcp/<MATRiX_IP>:7447`。
- 内置运动控制当前固定要求本机 `tcp/127.0.0.1:7447`。

`0.0.0.0` 用于监听，不应作为远程客户端要连接的目标地址。

## 统一时间与同步模式

所有相机、LiDAR、IMU、GPS、里程计和 robot-state 使用统一 `FRobotClock`。Header 遵循 ROS 2 `builtin_interfaces/msg/Time`：

~~~text
int32 sec
uint32 nanosec
~~~

异步模式使用绝对 deadline；负载无法维持目标频率时只采集当前样本、改用真实采集时间并重建相位，不会在一帧中批量补发过期数据。

同步模式只通过机器人级字段启用：

~~~json
"sensor_sync_mode": true
~~~

不要在单个传感器对象中写 `synchronized`。当前项目 JSON 也不再接受 `sensor_master_rate_hz`、`sensor_overrun_policy` 或 `require_realtime_sensor_frequency`。

默认公共频率边界为：

- IMU 与 robot-state：500 Hz / 2 ms。
- GPS 与里程计：100 Hz / 10 ms。
- 相机与 LiDAR：10 Hz / 100 ms。

配置频率是目标值。相机/LiDAR 仍受渲染、GPU readback、编码、射线和队列负载限制；消息到达间隔也会受 Zenoh 和操作系统调度影响，不应直接等同于 Header 采样间隔。

## 跨机器工具示例

若下载的运行包包含 `Tools/`：

~~~bash
python3 Tools/zenoh_sensor_receiver.py --connect tcp/192.168.1.100:7447
python3 Tools/zenoh_topic_monitor.py --connect tcp/192.168.1.100:7447
~~~

同时确认 MATRiX 侧确实在 `0.0.0.0:7447` 监听，并放行 TCP 7447。
