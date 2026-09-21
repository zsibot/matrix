# BBox / 激光雷达 / 图像录制与回放

## 启动

在 MATRiX 发布包根目录执行：

```bash
python3 Tools/zenoh_bbox_lidar_recorder.py
```

也可以指定路由器地址：

```bash
python3 Tools/zenoh_bbox_lidar_recorder.py --connect tcp/127.0.0.1:7447
```

界面使用 Tkinter。录制、离线预览和回放不依赖 NumPy、Matplotlib 或 OpenCV。
JPEG/PNG 图像显示需要 Pillow：`python3 -m pip install Pillow`。未安装时仍可录制、回放和重新发布原始图像消息，预览区会提示安装依赖。
连接 Zenoh 需要 `eclipse-zenoh`。Ubuntu 用户可按需安装：

```bash
sudo apt install python3-tk
python3 -m pip install eclipse-zenoh
```

请将 `zenoh_bbox_lidar_recorder.py`、`zenoh_recording.py` 与 `bbox_motion.py` 放在同一目录。独立复制 `visualize_zenoh_bbox.py` 时也需要带上 `bbox_motion.py`。

## 新版目标消息预览

支持 `目标名称 → {category, bbox, velocity, speed, velocity_unit}`，也兼容旧版平铺 BBox 和无速度字段的录制。

- 标签显示目标名称、类别和速率（m/s）；蓝色车辆、橙色行人、灰色其他目标。
- 绿色箭头表示 ROS 世界 XY 速度的一秒位移，不等同于模型朝向。三维速率包含 Z 分量。
- 无速度或无效速度显示“速度未知”，显式零速度显示 `0.00 m/s`。
- 支持 `m/s`、`cm/s`、`km/h` 速度单位；有效速度向量优先用于计算速率。
- 预览解析不修改原始录制和回放消息。

## 录制

1. 启动仿真与 Zenoh 路由器，确认界面地址与仿真连接的路由器一致。
2. 检查订阅主题。默认包含 `rt/dynamicinfo` 和 `rt/front_camera/image/compressed`，并从
   `UeSim/Content/model/config/sensors/config_data.json` 自动读取已启用的雷达主题。
   当前配置为 `rt/front_lidar`。多个主题使用英文逗号分隔，例如：
   `rt/dynamicinfo, rt/front_lidar, rt/rear_lidar`。
3. 点击 **开始读取** 查看接收数量和俯视预览。
4. 点击 **开始录制…**，选择新的 `.uesimrec` 文件。也可从未连接状态直接开始录制，程序会自动连接。
5. 点击 **结束录制**，等待队列写完。文件保存完毕后仍可继续实时预览；
   **停止读取** 会同时结束录制并断开连接。

开始读取本身不保存历史消息，只有开始录制之后接收的消息写入文件。
不允许覆盖已有录制文件。关闭窗口时会先停止读取并保存已接受的数据。

## 回放

1. 停止实时读取。
2. 点击 **打开录制文件…**，选择 `.uesimrec`。
3. 选择倍速（0.25、0.5、1、2、4），点击 **播放**。
4. 使用 **暂停 / 继续**；**停止播放** 后再次播放会从头开始。

默认离线回放，不需要 Zenoh 路由器。界面分别显示 bbox 与选中雷达的 XY 俯视图，
以及选中相机的图像。图像主题下拉框自动列出收到的 `*/image/compressed` 主题，
支持 ROS2 CompressedImage XCDR1 中的 JPEG/PNG，也支持这些主题上的原始 JPEG/PNG。
实时读取和文件回放均显示图像，按比例缩放适应窗口；预览约每 0.25 秒抽取最新帧，
录制仍保存接收到的每条原始图像消息，不缩放、不重新压缩。旧录制文件没有图像主题时显示等待提示。
可切换雷达主题及显示半径。BBox 自动缩放；两个视图未进行外参转换或坐标配准。
每次雷达预览最多抽样 1800 个点，**录制文件中的点云完整保留**。
预览支持项目的双重 JSON 编码 bbox 和小端 XCDR1 ROS2 PointCloud2 浮点 XYZ。
其他传感器格式可以保存和重新发布，但未提供图形解码。

若要让已有工具接收回放数据，播放前勾选 **重新发布到原 Zenoh 主题**。
先停止仿真端同主题发布，避免实时消息与回放消息混合，再运行现有可视化程序，例如：

```bash
python3 Tools/visualize_zenoh_bbox.py
python3 Tools/zenoh_sensor_receiver.py --help
```

回放保留原 topic、payload 和 encoding。按录制端的单调时钟接收时间排序并调度，
倍速等比例缩放消息间隔。原消息内的传感器时间戳不变，**不会改写为当前时间**；
这不是严格的传感器采样同步，也不是 ROS bag 文件。Zenoh 的网络 timestamp/attachment
不单独保存。仅回放文件内容，不重建仿真场景。

## 文件与异常处理

`.uesimrec` 是 SQLite 数据库，数据不压缩：

- `messages`：递增序号、相对接收时间（纳秒）、topic、encoding、原始 payload。
- `metadata`：格式版本、创建时间、订阅主题、完成标志、队列溢出丢帧计数。

后台线程写盘并定期提交。缓存最多 128 MiB，队列满时停止录制并明确报错，
文件标记为不完整；已经接受的队列数据会继续写完。磁盘写入错误也会在界面显示。
正常结束会完整提交并合并 WAL。录制期间不要移动数据库文件；若程序异常退出，
保留同目录下可能存在的 `-wal` 和 `-shm` 文件，可打开并回放已提交的数据。
崩溃前尚未提交的消息可能丢失；界面会提示文件未正常结束。

点云数据量较大，请关注磁盘剩余容量和界面的排队数据量。
程序计数反映实际收到/保存的消息，不能检测仿真发布端或网络在到达本程序之前的丢包。
