# MATRiX v1.0.13 快速开始

[返回中文主页](README_CN.md) | [English](Getting_Started.md)

## 1. 下载与解压

可从[百度网盘](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q)下载完整 Linux 运行包（提取码 `118g`），也可从 [v1.0.13 GitHub Release](https://github.com/zsibot/matrix/releases/tag/v1.0.13) 下载全部 3 个压缩分片及 `SHA256SUMS`。使用 GitHub 分片时执行：

```bash
sha256sum -c SHA256SUMS
cat MATRiX_v1.0.13.tar.gz.part-* | tar -xzf -
```

分片大小和完整校验值见[下载与校验](Release_Download_CN.md)。

## 2. 启动

要求 Linux x86_64 环境并正确安装显卡驱动，不限定 Ubuntu 22.04。建议 6 核以上 CPU、16 GB 以上内存。仿真器本体不依赖 ROS 2。

```bash
cd MATRiX_v1.0.13
./UeSim.sh
```

不需要对 `UeSim.sh` 或 `UeSim/Binaries/Linux/UeSim` 执行 `chmod`。

启动参数会原样传给 UeSim：

```bash
./UeSim.sh -ResX=1280 -ResY=720 -Windowed
```

日志在首次启动后生成：

```text
UeSim/Saved/Logs/UeSim.log
```

## 3. 配置与模型

主配置：

```text
UeSim/Content/model/config/config.json
```

发布默认值：

```text
mujoco_model: model/xgb/xgb.xml
inside_mc: true
network_mode: standalone
sensor_sync_mode: false
zenoh_router: tcp/0.0.0.0:7447
state_port: mujoco/state
cmd_port: mujoco/cmd
```

模型路径使用相对于 UeSim Content 的路径，移动整个发布目录后仍然有效。当前主要模型目录：

```text
go2  go2w  xg2  xgb  xgw  xgw2  xxg  zgws  zgwsarm  zgwt
```

## 4. 运动控制

默认使用内置运控，不需要下载或安装独立控制器：

```bash
./UeSim.sh
```

本发布包不包含独立 `robot_mc`。需要时自行下载，并按 [运动控制指南](Motion_Control_CN.md#4-可选独立-robot_mc需另行下载) 手动修改 `inside_mc`。修改后必须重启 UeSim，且两种控制器不能同时运行。

## 5. Zenoh 与传感器

UeSim 默认监听 `tcp/0.0.0.0:7447`，本机工具连接 `tcp/127.0.0.1:7447`。

按需安装 Python 工具依赖：

```bash
python3 -m pip install eclipse-zenoh numpy opencv-python matplotlib
```

发现实际主题：

```bash
python3 Tools/zenoh_topic_monitor.py --key '**'
python3 Tools/zenoh_topic_monitor.py --key 'rt/**'
python3 Tools/zenoh_sensor_receiver.py --key 'rt/**'
```

远端连接：

```bash
python3 Tools/zenoh_topic_monitor.py \
  --connect tcp/192.168.1.100:7447
```

默认配置包含 IMU、里程计、GPS、RGB、深度和 Airy LiDAR。界面或传感器预设可能修改活动配置，最终 key 以监控器收到的数据为准。

传感器预设：

```text
UeSim/Content/model/config/sensors/
```

## 6. 工具

| 工具 | 用途 |
|---|---|
| `matrix_mc_udp_test.py` | 内置运控 UDP 控制示例 |
| `zenoh_topic_monitor.py` | Zenoh 主题、频率和延迟监控 |
| `zenoh_sensor_receiver.py` | 图像、深度和点云接收 |
| `visualize_lidar_camera_projection.py` | LiDAR 到相机投影 |
| `visualize_zenoh_bbox.py` / `_2d.py` | 3D/2D 包围盒显示 |
| `gimbal_udp_client.py` / `_ui.py` | 云台控制和测试 |

准确参数以对应脚本的 `--help` 为准。

### LiDAR 到相机图像投影

```bash
python3 -m pip install numpy opencv-python eclipse-zenoh

# 先检查传感器选择、内参和外参，不连接 Zenoh
python3 Tools/visualize_lidar_camera_projection.py --check-only

# 启动实时叠加窗口
python3 Tools/visualize_lidar_camera_projection.py
```

工具默认读取 `UeSim/Content/model/config/config.json`，并连接 `tcp/127.0.0.1:7447`。使用前必须设置 `sensor_sync_mode=true`，并建议相机和 LiDAR 使用相同频率与相同 `sensor_attach`。详细说明见 [Lidar_Camera_Projection_CN.md](Lidar_Camera_Projection_CN.md)。

## 7. DLC 地图

基础开源发布目录不附带外部地图 DLC，且 `UeSim/Content/model/MapDataTable.json` 初始为合法的空目录。第一次进入地图界面没有地图卡片属于正常现象。先点击 **UPDATE LIST** 获取最新地图列表，再点击目标地图下方的 **DOWNLOAD** 按钮自动下载对应 DLC。

自动下载不可用时，可从 [百度网盘（提取码：6sth）](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F) 手动下载。

将获得授权且与 v1.0.13 匹配的 `.pak` 放入：

```text
UeSim/Saved/DLCs/
```

目录不存在时可创建：

```bash
mkdir -p UeSim/Saved/DLCs
cp /path/to/MapBundle.pak UeSim/Saved/DLCs/
```

重启 UeSim 后在地图界面选择。若 `.pak` 已安装但没有对应卡片，先更新目录；完整说明见 [地图目录与 DLC](Map_DLC_CN.md)。

## 8. ROS 2 与 Pixel Streaming

运行包以 Zenoh 为主要传输。ROS 2 集成需要与当前消息格式匹配的 bridge，详见 [RoamerX_Lite_Integration.md](RoamerX_Lite_Integration.md)。

Pixel Streaming 2 服务器下载入口：

```text
UeSim/Samples/PixelStreaming2/WebServers/get_ps_servers.sh
```

详见 [pixelstreaming_tutorial.md](pixelstreaming_tutorial.md)。

## 9. 排查

模型找不到时，确认 `mujoco_model` 指向存在的相对路径。黑屏、崩溃或 Vulkan 错误时查看：

```bash
tail -n 200 UeSim/Saved/Logs/UeSim.log
```

Zenoh 无数据时先订阅 `**`，再核对 UeSim 日志、IP、7447/TCP、防火墙和传感器状态。
