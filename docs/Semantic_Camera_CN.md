# 普通语义相机

`RobotSensorSimulation` 的 `ARobotCameraSensorActor` 支持 `SensorType = Semantic`，JSON 类型为 `semantic`。这是透视语义真值相机：使用场景 Actor Tags 生成类别图，不运行视觉识别模型。支持与 RGB 相同的针孔内参和 Brown–Conrady 畸变；不提供全景或鱼眼语义输出。

## 使用随包方案

本说明对应 2026-09-23 10:24（北京时间）重打包的 v1.1.2。初始传感器为空；`config_default.json` 六传感器预设不含语义相机。在传感器设置中加载并应用 `UeSim/Content/model/config/sensors/config_rgb_semantic.json`，进入仿真后运行下方接收器，即可同时订阅 RGB 和语义话题。仅需要语义图时使用 `config_semantic.json`。配对预设为 640×480、10 Hz、90° FOV，两路安装位姿与标定参数相同。

## 类别与输出

相机、Airy CPU/GPU、MID360 CPU/GPU、通用 LiDAR 共用 `RobotSemanticLabels::Resolve`。

| Actor Tag | 类别 ID |
|---|---:|
| 无有效可见表面 | 0 |
| `drive_plane` | 10 |
| `drive_stair` | 20 |
| `drive_other` | 30 |
| `human` | 40 |
| `vehicle` | 50 |
| 可见但未分类的物体 | 255 |

多个标签同时存在时，按表中标签顺序匹配。读取 Actor Tags，不读取 Component Tags；一个 Actor 的可渲染组件使用相同类别。雷达的未命中处理保持原行为；相机额外约定背景为 0。

输出沿用 ROS2 `sensor_msgs/msg/CompressedImage` / Zenoh 发布链路，**始终为无损 PNG**，即使 `ImageEncoding` 被设置为 JPEG。解码为 RGBA/BGRA 后，`R=G=B=类别 ID`，`A=255`。该图是类别数据，不能再做颜色空间变换、有损压缩或双线性缩放。

默认话题模板为 `/front_camera/semantic/image/compressed`；SpawnManager 沿用项目约定添加 `rt` 前缀。未分类遮挡物输出 255，不透出后方物体的类别。

## 与 RGB 对应

1. 从 RGB 配置复制一份传感器，使用新名称，并把 `sensor_type` 改为 `semantic`、`topic` 改为独立话题。模板见 `UeSim/Content/model/config/sensors/config_semantic.json`。
2. 保持 `sensor_attach`、`position`、`rotation`、`width`、`height`、`fov`、`fx/fy/cx/cy`、`K1/K2/K3/P1/P2` 和 `ignore_mounting_actor` 相同。
3. 使用相同 `frequency`，在机器人配置中设置 `robot.sensor_sync_mode = true`。直接使用 Actor 时，为同一机器人上的两个相机启用 `bUseSynchronizedMode`，必要时设置相同的 `SensorSyncGroup`；触发延迟、曝光时间和时间戳参考也应一致。
4. 直接使用 Actor 的高级设置时，保持 `PerspectiveDistortionMaxOverscanFactor` 相同。云台相机还需共享实际光学位姿，单独复制初始外参不会同步云台运动。

`K1/K2/K3` 为径向系数，`P1/P2` 为切向系数。五个系数为零时使用普通透视投影；非零时复用 RGB 的逆映射、视场扩展和非法参数回退逻辑。类别图采用最近邻采样，不执行 RGB 的双线性颜色插值和 sRGB 转换，因此几何映射一致，边缘保持单一类别。

在蓝图中也可直接 Spawn `RobotCameraSensorActor`，设置 `SensorType = Semantic`，配置镜头参数后调用 `StartSensor()`。现有 `SetPerspectiveCameraIntrinsics`、`SetPerspectiveDistortionParameters` 和 `SetOpenCvPerspectiveDistortionParameters` 接口均适用。

## 渲染边界

- 需要 `r.CustomDepth=3`，本项目已经启用。仅针对当前桌面延迟渲染路径实现。
- 标签在 GPU 中从 SceneDepth / CustomDepth / CustomStencil 提取到独立线性 RenderTarget，不经过光照、曝光或色调映射；用深度一致性检查阻止被遮挡标签和仅写 CustomDepth 的辅助几何污染结果。
- 活跃语义相机共享世界内的 Stencil 使用权。每个采集帧更新 Actor 标签和已注册组件；最后一个使用者停止或销毁时恢复组件原来的 CustomDepth、Stencil ID 和写掩码。运行期间不要让其他效果同时改写这些值；依赖原有 Stencil 的轮廓或后处理效果需要另行协调。
- 普通不透明网格已通过渲染测试。透明材质、特殊自定义渲染器、Gaussian Splat 等没有在本次验证中覆盖；能否得到类别取决于是否提供相应深度/Stencil。相机基于可见渲染表面，雷达基于碰撞表面，两者的轮廓可能不同。
- 类别图不混合边缘像素；RGB 的抗锯齿或运动模糊可能混合颜色，不能以边缘颜色完全相同作为对齐标准。

## 接收与显示

`Tools/zenoh_sensor_receiver.py` 的默认 `auto` 模式通过话题或 frame 名称中的 `semantic` / `segmentation` 识别语义 PNG。同一接收器可同时打开 RGB 和语义窗口，例如在解压的运行包根目录运行：

```bash
python3 Tools/zenoh_sensor_receiver.py --key 'rt/front_camera/**'
```

显示使用固定类别配色及图例，鼠标悬停显示原始类别 ID 和标签名称；终端输出各类别的像素数量。背景 0 与未分类 255 分别显示为黑色和灰色。未定义的 ID 显示为品红色，保留原值供检查。着色和鼠标标记不修改原始标签数组。

如果自定义话题不包含上述识别词，限定订阅该语义话题并显式指定：

```bash
python3 Tools/zenoh_sensor_receiver.py --key 'rt/custom_labels/**' --stream-type semantic
```

语义解码要求无损 8 位 PNG（单通道或 R=G=B，RGBA 的 A=255）；JPEG、彩色预览 PNG 或 16 位图不会被当作原始类别图解码。
