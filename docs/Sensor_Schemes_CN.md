# MATRiX v1.1.2 传感器配置

[使用教程](Getting_Started_CN.md) | [English](Sensor_Schemes.md)

## 活动配置与方案文件

主配置为 `UeSim/Content/model/config/config.json`。初始 `robot.sensors` 为空，不会自动发布传感器数据；`sensor_sync_mode=true`。请在传感器设置中加载并应用 `config_default.json`（IMU、Odom、GPS、RGB、Depth、Airy）或其他方案，再进入仿真并创建机器人。 方案文件不会仅因存在于磁盘就自动启用。

在机器人/传感器设置中加载 `UeSim/Content/model/config/sensors/` 下的方案，检查挂载对象、频率和 topic，应用后再进入仿真。以保存到主配置的 `robot.sensors` 和实际收到的数据为准。手工编辑时先退出 UeSim，把方案 JSON 的传感器字典放入 `robot.sensors`；不要用方案文件直接覆盖整个 `config.json`，以免丢失模型和网络设置。

首次验证建议使用 `config_default.json`。所有 `--sensor-config` 工具参数只选择工具读取的配置，不会修改仿真器配置或激活传感器。

## 随包方案

| 文件 | 内容 |
|---|---|
| `config_default.json` | IMU、Odom、GPS、RGB、Depth、Airy |
| `config_data.json` | 前雷达 IMU、Odom、GPS、已设内外参的 RGB、MID360 |
| `mid360_slam.json` | MID360、Odom、IMU |
| `config_lidar.json` | MID360 与 Airy |
| `config_dual_airy_gpu.json` | 前后双 Airy、GPU 后端与运动畸变 |
| `config_surround4_airy_calibration_approx.json` | 四路鱼眼、前后 Airy、IMU、Odom；近似标定 |
| `config_zg.json` | RGB 与 Airy |
| `config_v1.0.12_zgwt.json` | 三路 IMU、Odom、GPS、前后相机及 Airy；保留历史文件名 |
| `config_all_sensors.json` | 11 类传感器示例，负载较高 |
| `config_fisheyecamera.json` | 鱼眼 |
| `config_panorama.json` | 全景 RGB |
| `config_ptzrgb.json` | 云台 RGB |
| `config_infrared.json` | 红外 |
| `config_semantic.json` | 透视语义相机，类别 ID PNG |
| `config_rgb_semantic.json` | 相同位姿、内参和频率的 RGB/语义配对 |
| `empty.json` | 空方案 |

本次重打包已包含 `config_semantic.json`（语义相机）和 `config_rgb_semantic.json`（同位姿 RGB/语义配对）。输出无损类别 ID PNG；使用 `zenoh_sensor_receiver.py` 可按类别着色查看。初始传感器为空，语义方案需要另行选择并应用。

## 参数与 GPU 雷达

- `enabled` 决定是否启用；`frequency` 为 Hz，位置为米，旋转为度；`sensor_attach` 需与实际模型挂载对象匹配。
- 透视相机支持 `fx/fy/cx/cy` 与 `K1/K2/K3/P1/P2`。`fx/fy=0`、`cx/cy=-1` 表示使用 FOV/图像中心默认值，不是实际零焦距。
- Airy 和 MID360 使用统一的 `backend` 字段，值为 `gpu` 或 `cpu`。多个随包方案请求 GPU；需要可用的 NVIDIA CUDA/OptiX 驱动环境。以启动日志的实际 `backend` 为准，不能仅凭配置判断。
- 随包 GPU 文件位于 `UeSim/Plugins/RobotSensorSimulation/Binaries/Linux/`，包含 `libAiryOptix.so` 和 `AiryOptix.ptx`。不要移动其中的依赖文件。
- GPU 初始化不可用时实现可回退到 CPU；若需明确使用 CPU，将所选方案内各雷达的 `backend` 改为 `cpu` 并重新应用。运行中 GPU 错误会停止受影响传感器，需要检查日志。
- `simulate_motion_distortion` 决定滚动扫描运动畸变。做静态投影核对时先停稳或关闭该项；Header 相同不代表逐点去畸变。
- Airy 的 `RangeBiasMeters`、`RangeNoiseStdDevMeters`、`ReturnDropoutProbability`、`MeasurementRandomSeed` 控制测量误差；默认零噪声不是实物设备指标。

`config_all_sensors.json` 和四路环视方案会增加渲染、GPU 和网络负载，性能需在目标显卡和地图上实测。

当前统一发布器的图像/点云 Header 使用 `frame_id=map`，但雷达 XYZ 仍是传感器局部 ROS FLU 坐标；桥接时不能按标签直接当作世界点云。Airy RoboSense 有组织点云的 `timestamp` 是绝对秒，MID360 逐点时间使用独立约定，详见 [消息与坐标说明](Lidar_Camera_Projection_CN.md)。

## 接收与核对

在发布包根目录运行（先按 [工具说明](../Tools/README.md) 安装依赖）：

```bash
python3 Tools/zenoh_topic_monitor.py --key '**'
python3 Tools/zenoh_sensor_receiver.py --key 'rt/**'
# 仅离线核对默认方案的相机与雷达，不启动仿真或连接网络
python3 Tools/visualize_lidar_camera_projection.py \
  --sensor-config UeSim/Content/model/config/sensors/config_default.json --check-only
# 核对四路鱼眼方案
python3 Tools/visualize_lidar_fisheye_projection.py --check-only
```

没有数据时，先确认机器人和传感器已经在场景中生成、活动配置不是空方案，再检查 topic 和 TCP 7447。常见方案的 `/front_lidar`、`/front_camera/image/compressed` 在 Zenoh 上通常对应 `rt/front_lidar`、`rt/front_camera/image/compressed`，最终以监控结果为准。

[Semantic camera / 语义相机使用说明](Semantic_Camera_CN.md)
