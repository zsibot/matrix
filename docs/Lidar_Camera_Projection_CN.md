# MATRiX LiDAR 到相机投影工具与传感器坐标系说明

[返回中文主页](README_CN.md) | [English](Lidar_Camera_Projection.md)

本文面向使用 MATRiX/UeSim 传感器数据的开发人员，配套工具为
`Tools/visualize_lidar_camera_projection.py`。工具直接订阅 Zenoh 上的 ROS 2
XCDR1 消息，只使用刚性安装的相机、LiDAR 和固定外参，不订阅 IMU、里程计，
也不执行 SLAM 或运动补偿。

## 1. 安装与启动

### 1.1 依赖

```bash
python3 -m pip install numpy opencv-python eclipse-zenoh
```

### 1.2 本机运行

先启动 MATRiX 仿真器，再在发布包根目录执行：

```bash
cd /path/to/MATRiX_v1.0.13
python3 Tools/visualize_lidar_camera_projection.py
```

默认读取：

```text
UeSim/Content/model/config/config.json
```

默认连接 UeSim 内嵌 Zenoh router：

```text
tcp/127.0.0.1:7447
```

按 `S` 保存当前叠加图，按 `Q` 或 `Esc` 退出。保存目录默认为
`Saved/LidarCameraProjection/`。

### 1.3 常用参数

```bash
# 只检查传感器选择、内参和外参，不连接 Zenoh
python3 Tools/visualize_lidar_camera_projection.py --check-only

# 指定配置文件
python3 Tools/visualize_lidar_camera_projection.py \
  --sensor-config UeSim/Content/model/config/config.json

# 配置中有多个相机或 LiDAR 时明确选择名称
python3 Tools/visualize_lidar_camera_projection.py \
  --camera-name camera --lidar-name lidar

# 覆盖 Zenoh key
python3 Tools/visualize_lidar_camera_projection.py \
  --camera-key rt/front_camera/image/compressed \
  --lidar-key rt/front_lidar

# 连接远端 MATRiX
python3 Tools/visualize_lidar_camera_projection.py \
  --connect tcp/192.168.1.100:7447

# 严格要求相机和 LiDAR Header 纳秒完全相等
python3 Tools/visualize_lidar_camera_projection.py --max-time-diff 0

# 兼容旧数据时，先找完全相等的 Header，失败后允许 5 ms 内最近邻配对
python3 Tools/visualize_lidar_camera_projection.py --max-time-diff 0.005
```

工具要求设置 `sensor_sync_mode=true`。相机与 LiDAR 还应使用相同 `frequency` 和相同 `sensor_attach`：

```json
"sensor_sync_mode": true
```

工具画面中的 `dt` 是相机 Header 减 LiDAR Header。快速运动测试时应优先使用
`dt=0`；旧发布包不能生成完全相等 Header 时，5 ms 最近邻只是兼容模式，不等于
硬件触发同步。

## 2. 外参与相机内参

### 2.1 直接从 UeSim 配置计算

当相机和 LiDAR 的 `sensor_attach` 相同，工具根据两者在共同刚体上的
`position`、`rotation` 自动计算固定外参。

本文统一使用记号：

```text
T_A_B：把 B 坐标系中的点转换到 A 坐标系
p_A = R_A_B p_B + t_A_B
```

自动计算过程为：

```text
T_camera_optical_lidar
  = T_camera_optical_camera_body
  · inverse(T_base_camera_body)
  · T_base_lidar
```

透视投影为：

```text
[Xc, Yc, Zc, 1]^T = T_camera_optical_lidar · [Xl, Yl, Zl, 1]^T
u = fx · Xc / Zc + cx
v = fy · Yc / Zc + cy
```

只投影 `Zc > 0` 的点。

### 2.2 使用真实标定结果

真实设备应优先使用标定得到的外参和相机内参：

```json
{
  "T_camera_optical_lidar": [
    [0.0, -1.0, 0.0, -0.010512812],
    [1.0,  0.0, 0.0, -0.114149652],
    [0.0,  0.0, 1.0, -0.059982609],
    [0.0,  0.0, 0.0,  1.0]
  ],
  "fx": 794.93,
  "fy": 794.93,
  "cx": 959.5,
  "cy": 539.5,
  "width": 1920,
  "height": 1080
}
```

运行：

```bash
python3 Tools/visualize_lidar_camera_projection.py \
  --calibration-json calibration/lidar_camera.json
```

矩阵平移单位必须是米。若标定软件给出的是 `T_lidar_camera_optical`，必须先求逆：

```text
T_camera_optical_lidar = inverse(T_lidar_camera_optical)
```

普通 RGB 路径使用针孔模型，并应用配置或标定 JSON 中的
Brown–Conrady `k1/k2/p1/p2/k3` 畸变参数。鱼眼和全景图不使用该针孔投影路径。

## 3. MATRiX/UeSim 基础坐标约定

### 3.1 UE 内部坐标

| 项目 | 定义 |
|---|---|
| 单位 | 厘米 |
| X | 前 |
| Y | 右 |
| Z | 上 |
| 手性 | UE 左手坐标系 |

### 3.2 发布后的 ROS/MuJoCo 坐标

| 项目 | 定义 |
|---|---|
| 单位 | 米；角速度 rad/s；加速度 m/s² |
| X | 前 |
| Y | 左 |
| Z | 上 |
| 手性 | 右手，FLU，符合 ROS REP-103 机器人本体约定 |

UE 向 ROS 的位置/普通向量转换为：

```text
C = diag(1, -1, 1)
p_ros[m] = 0.01 · C · p_ue[cm]
R_ros = C · R_ue · C
q_ros(x,y,z,w) = (-q_ue.x, q_ue.y, -q_ue.z, q_ue.w)
```

注意：点云发布器已经执行米制转换和 Y 翻转。Python/ROS 收到
`PointCloud2` 后不要再次执行 `y=-y`。

### 3.3 配置文件中的安装位姿

`position` 使用米，按安装父坐标系的 X 前、Y 左、Z 上填写。当前 SpawnManager
对 JSON 欧拉角的兼容映射为：

```text
R_base_sensor = Rz(+yaw) · Ry(-pitch) · Rx(-roll)
```

也就是工具中的 `sensor_pose_in_ros_attach()`。这不是通用标定文件约定；从其他
软件复制 RPY 前必须确认旋转顺序、角度单位以及矩阵方向。建议跨系统交换时直接保存
4×4 齐次矩阵。

## 4. 每类传感器的坐标系与消息

### 4.1 RGB、红外和深度相机

相机安装本体坐标 `camera_body` 使用 FLU：X 前、Y 左、Z 上。针孔投影使用
OpenCV/ROS optical 坐标 `camera_optical`：

| optical 轴 | 方向 |
|---|---|
| X | 图像右 |
| Y | 图像下 |
| Z | 镜头前方 |

从 camera body 到 optical 的旋转为：

```text
R_camera_optical_camera_body =
[[ 0, -1,  0],
 [ 0,  0, -1],
 [ 1,  0,  0]]
```

图像像素原点在左上角，`u` 向右、`v` 向下。RGB/红外发布
`sensor_msgs/msg/CompressedImage`。深度相机可发布压缩可视化图和原始深度；
`OpticalAxisZ` 表示沿 optical Z 的深度，`RadialRange` 表示到光心的欧氏距离，
二者不能混用。

### 4.2 PTZ 相机

PTZ 图像的 optical 坐标定义与普通相机相同，但外参随云台角度变化。只有在云台不动，
或 LiDAR 与相机安装在同一云台刚体上时，才能使用固定
`T_camera_optical_lidar`。LiDAR 固定在机器人而相机独立转动时，需要订阅云台实时姿态
并逐帧更新外参，本工具的固定外参模式不适用。

### 4.3 全景相机

全景图采用等距柱状投影：

- 图像中心 `(u=0.5, v=0.5)` 指向相机本体 +X 前方；
- 图像右侧沿水平方向转向本体右侧，即 FLU 的 -Y；
- 图像上方为 +Z；
- 左右边界对应后方，顶部/底部分别对应天顶/地底。

普通针孔 `u=fx·x/z` 不适用于全景图。

### 4.4 鱼眼相机

鱼眼图中心指向本体 +X；像素右为本体右侧，像素下为本体下方。UeSim 使用
Kannala–Brandt 形式：

```text
rd = θ + k1·θ³ + k2·θ⁵ + k3·θ⁷ + k4·θ⁹
```

鱼眼图必须使用相同模型和参数投影，不能直接套用普通相机内参。

### 4.5 Airy LiDAR

发布类型为有组织的 `sensor_msgs/msg/PointCloud2`：

```text
x, y, z       float32，米，LiDAR FLU 坐标
intensity     float32
ring          uint16
timestamp     float64，点相对帧时刻的纳秒偏移
```

坐标轴为 X 前、Y 左、Z 上。无回波射线保留为 NaN 槽，消息
`is_dense=false`；消费者必须先过滤非有限 XYZ，不能把 NaN 当作零点。真实 RoboSense
Airy 的产品坐标原点定义在 LiDAR 底座中心，设备还带独立 IMU 外参；使用真实设备时应从
RoboSense SDK/DIFOP 读取该批次标定值，不要假设 IMU 与 LiDAR 原点重合。

### 4.6 MID360 LiDAR

发布类型为 Livox 风格的非组织 `PointCloud2`：

```text
x, y, z       float32，米，LiDAR FLU 坐标
intensity     float32
tag           uint8
line          uint8
timestamp     float64，点时间字段
```

消息通常为 `height=1, width=N`，默认 `frame_id=livox_frame`。UeSim 输出已经统一为
ROS FLU。真实 Livox MID-360 原始协议可输出毫米整数坐标，官方
`livox_ros_driver2` 的 PointXYZRTLT 则输出米；接入真实包时必须先确认单位和
`timestamp` 是绝对时间还是相对 `timebase` 的偏移。

### 4.7 通用 LiDAR

`sensor_type=lidar` 同样发布 FLU、米制点云。具体字段以收到的 `PointCloud2.fields`
为准，不要按字节偏移硬编码；至少应按字段名读取 `x/y/z`，同时遵守
`point_step`、`row_step` 和大小端标记。

### 4.8 IMU

发布 `sensor_msgs/msg/Imu`：

- 传感器局部坐标按 FLU；
- `orientation` 为传感器姿态四元数，字段顺序 XYZW；
- `angular_velocity` 单位 rad/s；
- `linear_acceleration` 单位 m/s²；
- 当前全零 covariance 表示协方差未知。

依据 ROS REP-145，真实 IMU 驱动必须输出右手坐标。常见真实设备输出 NED 或
机体系 FRD，不能直接当成 FLU 使用。

### 4.9 里程计

发布 `nav_msgs/msg/Odometry`：

- `header.frame_id` 通常为 `world` 或 `odom`；
- `child_frame_id` 通常为 `base_link`；
- pose 表示 `T_world_base_link`，位置单位米，世界坐标采用 Z 向上；
- twist 来自 MuJoCo 局部物体速度，按 child/body FLU 表达；
- 四元数顺序 XYZW，角速度 rad/s。

不要把 `world/odom` 的全局向量与 `base_link` 的局部向量直接相加，必须先旋转到
同一坐标系。

### 4.10 GPS/RTK

GPS 使用经纬高语义：局部世界 X 增加对应向东/经度增加，Y 增加对应向北/纬度增加，
Z 增加对应高度增加，即局部 ENU。经纬度是角度，高程是米，不能把经纬度差直接当米；
小范围可使用选定原点的 ENU，大范围应使用规范的大地坐标转换。

## 5. 常见真实设备坐标与转换

### 5.1 ROS FLU 与相机 optical RDF

```text
p_optical =
[[ 0, -1,  0],
 [ 0,  0, -1],
 [ 1,  0,  0]] · p_flu

p_flu =
[[ 0,  0,  1],
 [-1,  0,  0],
 [ 0, -1,  0]] · p_optical
```

Intel RealSense、Stereolabs ZED 以及多数 ROS 相机驱动均提供 `_optical_frame`
（X 右、Y 下、Z 前），但相机外壳的 `camera_link` 往往是 FLU。必须查看
`header.frame_id` 或 TF，不能根据 topic 名猜测。

### 5.2 FRD 到 FLU

飞控和部分 IMU 使用 X 前、Y 右、Z 下（FRD）：

```text
p_flu = diag(1, -1, -1) · p_frd
R_flu_frd = RotX(π)
```

这是绕 X 轴旋转 180°，可用于点、速度、角速度和协方差的坐标变换。

### 5.3 NED 到 ENU

GNSS/飞控常用 X 北、Y 东、Z 下（NED），ROS 局部世界常用 X 东、Y 北、Z 上
（ENU）：

```text
p_enu =
[[0, 1,  0],
 [1, 0,  0],
 [0, 0, -1]] · p_ned
```

### 5.4 NWU 到 ENU

若设备世界坐标为 X 北、Y 西、Z 上（NWU）：

```text
p_enu =
[[ 0, -1, 0],
 [ 1,  0, 0],
 [ 0,  0, 1]] · p_nwu
```

### 5.5 任意设备外参

若真实设备输出坐标为 D，希望统一到 UeSim/机器人 LiDAR 坐标 L：

```text
p_L = R_L_D · p_D + t_L_D
```

若厂商给的是反方向 `T_D_L=[R_D_L,t_D_L]`：

```text
R_L_D = transpose(R_D_L)
t_L_D = -transpose(R_D_L) · t_D_L
```

组合到相机：

```text
T_camera_optical_D = T_camera_optical_L · T_L_D
```

协方差也必须变换。三维向量协方差：

```text
Σ_A = R_A_B · Σ_B · transpose(R_A_B)
```

不要只改 XYZ 而遗漏四元数、角速度、加速度和 covariance。

## 6. 排错

### 没有窗口或一直等待

新版工具会立即显示等待页。根据计数判断：

- camera=0、LiDAR=0：确认 UeSim 已启动、7447 端口可达；
- 只有一路为 0：检查配置 topic 和 `--camera-key/--lidar-key`；
- 两路都有但无法配对：检查频率、`sensor_sync_mode` 和画面中的 Header delta；
- 使用 `--max-time-diff 0.005` 验证旧发布包，硬同步验证用 `0`。

### 有相机图但没有投影点

依次检查：

1. 是否选错 LiDAR 或相机；
2. 两者 `sensor_attach` 是否相同；
3. 点云是否已经是 FLU/米制，是否被重复翻转 Y 或缩放；
4. 使用的是 `camera_optical`，而不是 `camera_link`；
5. 外参方向是否需要求逆；
6. 图像分辨率是否与内参标定分辨率一致；
7. 鱼眼/全景图是否错误使用了针孔投影。

### 静止正确、移动错误

固定安装不需要修改外参。重点检查 Header 配对、发布队列延迟和单帧点云是否混入
旧点。先观察画面 `dt`，再分别记录相机/LiDAR Header；不要用 IMU/里程计去掩盖
本应刚性同步的数据错误。

## 7. 参考规范和设备资料

- ROS REP-103，标准单位和坐标约定：<https://www.ros.org/reps/rep-0103.html>
- ROS REP-105，`map/odom/base_link`：<https://www.ros.org/reps/rep-0105.html>
- ROS REP-145，IMU 驱动约定：<https://www.ros.org/reps/rep-0145.html>
- Livox MID-360 官方资料：<https://www.livoxtech.com/mid-360/downloads>
- Livox ROS Driver 2：<https://github.com/Livox-SDK/livox_ros_driver2>
- RoboSense Airy 官方资源：<https://www.robosense.ai/en/resources-161>
- RoboSense rslidar_sdk 坐标转换：<https://github.com/RoboSense-LiDAR/rslidar_sdk/blob/main/doc/howto/10_how_to_use_coordinate_transformation.md>
