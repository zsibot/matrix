# 鱼眼相机与 LiDAR 点云对齐可视化

入口为 `visualize_lidar_fisheye_projection.py`，需要同目录的
`visualize_lidar_camera_projection.py`、`fisheye_surround_viewer.py` 和
`fisheye_bbox_overlay.py`。在 MATRiX 发布包根目录执行：

```bash
python3 -m pip install numpy opencv-python eclipse-zenoh
python3 Tools/visualize_lidar_fisheye_projection.py --check-only
python3 Tools/visualize_lidar_fisheye_projection.py
```

默认读取 `UeSim/Content/model/config/sensors/config_surround4_airy_calibration_approx.json`，
默认四路相机拼成 2×2 窗口，连接 `tcp/127.0.0.1:7447`。

| 左列 | 右列 |
| --- | --- |
| 前 `surround_front` + `front_lidar` | 后 `surround_rear` + `rear_lidar` |
| 左 `surround_left` + `front_lidar` | 右 `surround_right` + `front_lidar` |

这是保留各自鱼眼画面的拼接显示，不是去畸变后的无缝全景。
每路按自己的相机/雷达 Header 配对，显示该路时间戳；单路缺帧不会阻塞其他路。
四路 bbox 和位姿的有效期统一在取得数据快照时判断，绘制前几路的耗时不会
使后几路误判过期。整张拼接完成后统一启动显示过期计时。
运行前确保 UE 已启动，实际加载的传感器方案与脚本一致，且 `sensor_sync_mode` 为 `true`。
脚本不会修改 UE 配置。

指定相机名称可切回单路窗口：

```bash
python3 Tools/visualize_lidar_fisheye_projection.py --camera-name surround_rear --lidar-name rear_lidar
python3 Tools/visualize_lidar_fisheye_projection.py --camera-name surround_left --lidar-name front_lidar
python3 Tools/visualize_lidar_fisheye_projection.py --camera-name surround_right --lidar-name rear_lidar
```

四路模式下 `--lidar-name rear_lidar` 可让所有相机使用后雷达；默认 `auto`
采用上表映射，不融合两个雷达的点云。

可用 `--sensor-config` 指定其他方案或完整配置，`--connect` 指定远端路由。
按 `S` 保存整张拼接叠加图到 `Saved/LidarFisheyeProjection`，按 `Q` 或 `Esc` 退出。
`--point-radius 0 --max-points 0` 显示所有投影点，每点一个像素。
默认严格匹配 ROS Header 纳秒时间戳；`--max-time-diff 0.005` 可显式允许
最多 5 ms 的最近帧匹配，但时间容差不能解决运动畸变。

## BBox 图像叠加

默认订阅与录制器相同的 `rt/dynamicinfo`，支持 actor 名称作为键、嵌套 `bbox`
以及双重 JSON 编码。使用消息中的八个 ROS 世界坐标角点绘制 12 条框边，
沿每条 3D 边采样后投影为鱼眼曲线，显示目标名称和类别。
车辆蓝色、行人橙色；中文名称在 OpenCV 标签里显示为 `?`。

默认从配置选择里程计（所给配置为 `Odom`，主题 `rt/odom`），
使用完整的平移和四元数姿态，将世界角点变换到每个相机的光学坐标。
`--bbox-pose-time-mode auto` 优先按相机 Header 插值；如果无法匹配，且同期
接收的里程计 Header 与相机相差超过 `max(0.5 秒, 3×pose gap)`，则显式
退回接收时间插值。终端每 5 秒提示一次，图像显示 `ego[receive]`、
机器人 XYZ、yaw 和 `dHeader`。一般丢帧、小时间差、过期里程计不会触发这个退回。
里程计必须与 bbox 使用同一个 ROS 世界原点及方向；重置为相对起点的外部
里程计不能直接用于这个转换。世界框使用真实 `corners`，不使用俯视图的 XY 框代替。

`dynamicinfo` 当前不包含采样 Header，bbox 只能按**接收时间近似匹配**，
默认容差和有效期为 0.3 秒，画面会明确标注 `receive-time approximate`。
无有效位姿、所选时间匹配模式无法匹配、bbox 过期时不画框；空快照清除目标。
线框不做场景深度遮挡剔除，并非实例分割轮廓。

```bash
# 自定义 bbox / 世界里程计 topic
python3 Tools/visualize_lidar_fisheye_projection.py --bbox-key rt/dynamicinfo --bbox-odom-key rt/odom
# 只看四路图像与点云
python3 Tools/visualize_lidar_fisheye_projection.py --no-bbox
```

可调参数：`--bbox-max-age 0.3`、`--bbox-pose-max-gap 0.1`、
`--bbox-odom-name Odom`。从录制器重新发布原主题时，录制中须包含四路图像、
所选雷达、bbox 和里程计；缺失里程计时仍显示点云，但不显示世界 bbox。

位姿时间匹配还支持 `--bbox-pose-time-mode header`（严格使用 Header，无法匹配就不画框）
和 `--bbox-pose-time-mode receive`（显式使用接收时间）。如果已标定固定时钟差，
可通过 `--bbox-odom-time-offset 秒数` 给里程计 Header 加偏移后匹配。
接收时间只能近似对应采样时刻，图像传输延迟和快速运动仍会带来误差；
准确同步应在发布端统一时钟，不能仅根据接收时刻硬编码一个 Header 偏移。

## 投影模型

实现依据本仓库 `RobotCameraProjection.usf` 的 `BuildProjectionDirection`
与 `RobotSensorActors.cpp` 的 `BuildCubeProjectionSample`，直接叠加原始鱼眼图像：

- 光学坐标 X 向右、Y 向下、Z 向前，使用 `theta = atan2(hypot(X,Y), Z)`。
- `rd = theta + K1*theta^3 + K2*theta^5 + K3*theta^7 + K4*theta^9`。
- 成像圆半径 `R = max(1, min((W-1)/2, (H-1)/2) * ImageCircleScale)`；
  等效焦距 `f = R / rd(fov/2)`，不是透视相机的正切公式。
- 支持 `ImageCircleScale`、`PrincipalPointOffsetX/Y`；与 UE 一致，
  scale 限制到 `[0.1, 2]`，有效 FOV 限制到 `[181, 360]` 度。
- 210° 的相机保留光轴夹角不超过 105° 的点，包括部分 Z<0 点；
  圆外不绘制点云，遮挡排序使用相机到点的欧氏距离。
- K1–K4 必须在有效视场内产生严格递增的半径，否则拒绝加载。

当前 960×768、210°、零畸变参数对应 `fx=fy≈209.266014`，
`cx=479.5`，`cy=383.5`。这些数值仅用于上述 UE 圆形鱼眼模型。
不能把普通透视模型的 Brown–Conrady 参数或其他鱼眼标定的 K/D 直接代入。

外参沿用工程现有安装位姿转换，配置平移单位为米、角度单位为度。
单路模式的 `--calibration-json` 可覆盖外参，文件仅需 `T_camera_optical_lidar` 的 4×4 矩阵
（或 `matrix`），方向为 LiDAR ROS 坐标到相机光学坐标。鱼眼参数仍取自传感器方案。

这是已有标定的投影检查工具，不会自动求解或优化标定。所给方案名称包含
`approx`，且两个雷达均启用 `simulate_motion_distortion`，建议停稳后检查边缘。
脚本不做逐点去畸变；同一 Header 时间戳不能消除扫描期间的运动误差。
