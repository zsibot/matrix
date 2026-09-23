# MATRiX v1.1.2 使用教程

[返回中文 README](README_CN.md) | [English](Getting_Started.md)

下载方式： [Linux 直链](http://39.96.31.125:18080/matrix/v1.1.2/Linux/MATRiX_v1.1.2.tar.gz)、[GitHub Release](https://github.com/zsibot/matrix/releases/tag/v1.1.2) 或 [百度网盘](https://pan.baidu.com/s/1dweDOFO5AzRmzY1-gEI53Q)（提取码 `118g`，**请选择最新版本下载**）。完整包直接解压；GitHub 下载全部分卷后校验合并。详细命令见 [下载与校验](Release_Download_CN.md)。

## 1. 启动

要求 Linux x86_64 环境并正确安装显卡驱动，不限定 Ubuntu 22.04。建议 6 核以上 CPU、16 GB 以上内存。仿真器本体不依赖 ROS 2。

```bash
cd MATRiX_v1.1.2
./UeSim.sh
```

启动参数会原样传给 UeSim：

```bash
./UeSim.sh -ResX=1280 -ResY=720 -Windowed
```

日志在首次启动后生成：

```text
UeSim/Saved/Logs/UeSim.log
```

## 2. 配置与模型

主配置：

```text
UeSim/Content/model/config/config.json
```

发布默认值：

```text
mujoco_model: Content/model/xgb/xgb.xml
inside_mc: true
network_mode: standalone
sensor_sync_mode: true
zenoh_router: tcp/0.0.0.0:7447
state_port: mujoco/state
cmd_port: mujoco/cmd
mujoco_running: false
sensors: {} (load and apply a scheme before receiving sensor data)
```

模型路径使用相对于 `UeSim/` 项目目录的路径，移动整个发布目录后仍然有效。当前主要模型目录：

```text
go2  go2w  xg2  xgb  xgw  xgw2  zgws  zgwsarm  zgwt
```

## 3. 运动控制

默认使用内置运控，不需要下载或安装独立控制器：

```bash
./UeSim.sh
```

本发布包不包含独立 `robot_mc`。需要时自行下载，并按 [运动控制指南](Motion_Control_CN.md#4-可选独立-robot_mc需另行下载) 手动修改 `inside_mc`。修改后必须重启 UeSim，且两种控制器不能同时运行。

## 4. Zenoh 与传感器

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

初始 `robot.sensors` 为空，不会自动发布传感器数据；`sensor_sync_mode=true`。请在传感器设置中加载并应用 `config_default.json`（IMU、Odom、GPS、RGB、Depth、Airy）或其他方案，再进入仿真并创建机器人。 GPU 后端以运行日志为准，最终 key 以主题监控结果为准。

传感器预设：

```text
UeSim/Content/model/config/sensors/
```

## 5. 工具

| 工具 | 用途 |
|---|---|
| `matrix_mc_udp_test.py` | 内置运控 UDP 控制示例 |
| `zenoh_topic_monitor.py` | Zenoh 主题、频率和延迟监控 |
| `zenoh_sensor_receiver.py` | 图像、深度和点云接收 |
| `visualize_lidar_camera_projection.py` | LiDAR 到相机投影 |
| `visualize_zenoh_bbox.py` / `_2d.py` | 分类与速度详情 / 固定范围 XY 包围盒视图 |
| `visualize_lidar_fisheye_projection.py` | 四路鱼眼点云与包围盒叠加 |
| `zenoh_bbox_lidar_recorder.py` | 原始消息录制、离线预览与回放 |
| `gimbal_udp_client.py` / `_ui.py` | 云台控制和测试 |

工具使用 Python 3.10+。完整依赖可在虚拟环境中通过 `python3 -m pip install -r Tools/requirements.txt` 安装。Tk 窗口另需系统 Tkinter；详见 [工具清单](../Tools/README.md)。准确参数以对应脚本的 `--help` 为准。

### LiDAR 到相机图像投影

```bash
python3 -m pip install numpy opencv-python eclipse-zenoh

# 先检查传感器选择、内参和外参，不连接 Zenoh
python3 Tools/visualize_lidar_camera_projection.py --sensor-config UeSim/Content/model/config/sensors/config_default.json --check-only

# 启动实时叠加窗口
python3 Tools/visualize_lidar_camera_projection.py
```

工具默认读取 `UeSim/Content/model/config/config.json`，并连接 `tcp/127.0.0.1:7447`。使用前必须设置 `sensor_sync_mode=true`，并建议相机和 LiDAR 使用相同频率与相同 `sensor_attach`。详细说明见 [Lidar_Camera_Projection_CN.md](Lidar_Camera_Projection_CN.md)。

## 6. DLC 地图

基础开源发布目录不附带外部地图 DLC，且 `UeSim/Content/model/MapDataTable.json` 初始为合法的空目录。第一次进入地图界面没有地图卡片属于正常现象。先点击 **UPDATE LIST** 获取最新地图列表，再点击目标地图下方的 **DOWNLOAD** 按钮自动下载对应 DLC。

自动下载不可用时，可从 [百度网盘（提取码：6sth）](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F) 手动下载。

将获得授权且与 v1.1.2 匹配的 `.pak` 放入：

```text
UeSim/Saved/DLCs/
```

目录不存在时可创建：

```bash
mkdir -p UeSim/Saved/DLCs
cp /path/to/MapBundle.pak UeSim/Saved/DLCs/
```

重启 UeSim 后在地图界面选择。若 `.pak` 已安装但没有对应卡片，先更新目录；完整说明见 [地图目录与 DLC](Map_DLC_CN.md)。

## 7. ROS 2 与 Pixel Streaming

运行包以 Zenoh 为主要传输。ROS 2 集成需要与当前消息格式匹配的 bridge，详见 [RoamerX_Lite_Integration.md](RoamerX_Lite_Integration.md)。

Pixel Streaming 2 服务器下载入口：

```text
UeSim/Samples/PixelStreaming2/WebServers/get_ps_servers.sh
```

详见 [pixelstreaming_tutorial.md](pixelstreaming_tutorial.md)。

## 8. 排查

模型找不到时，确认 `mujoco_model` 指向存在的相对路径。黑屏、崩溃或 Vulkan 错误时查看：

```bash
tail -n 200 UeSim/Saved/Logs/UeSim.log
```

Zenoh 无数据时先订阅 `**`，再核对 UeSim 日志、IP、7447/TCP、防火墙和传感器状态。

镜像独立同步；若尚无本版本，请使用 GitHub Release，并在百度网盘选择最新版本。
