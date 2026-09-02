# Python 工具指南

[← 返回项目首页](../README.md) · [中文文档索引](README_CN.md)

本指南记录部分运行包 `Tools/` 目录中的传感器接收器和 Zenoh 话题监控器。当前文档仓库与所核对的 `uesim` 源码快照均不包含这些脚本，因此下列命令只适用于确实附带 `Tools/` 的运行包；请先执行脚本的 `--help`，以当前参数为准。若需运动控制，请转到 [运动控制指南](Motion_Control_CN.md)。

## Python 工具

若发布包附带工具，它们位于 `Tools/` 目录，旧版工具通常需要 Python 3.10+。依赖版本和命令行参数不属于当前仿真源码的可验证接口。

### 安装依赖

```powershell
pip install eclipse-zenoh opencv-python numpy
```

---

### zenoh_sensor_receiver.py — 传感器数据接收器

订阅仿真器发布的传感器数据，自动识别图像并弹出 OpenCV 显示窗口，对点云和其他数据打印元信息。

#### 基本用法

```powershell
# 默认模式（本机 Router，监听 tcp/0.0.0.0:7447）
python zenoh_sensor_receiver.py

# 客户端模式，连接指定 Router
python zenoh_sensor_receiver.py --mode client --connect tcp/127.0.0.1:7447

# 仅订阅激光雷达话题
python zenoh_sensor_receiver.py --key "rt/front_lidar"

# 深度图启用伪彩色显示
python zenoh_sensor_receiver.py --show-depth

# 订阅 MuJoCo 所有话题
python zenoh_sensor_receiver.py --key "mujoco/**"
```

#### 参数列表

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--key` | `rt/**` | Zenoh key 表达式，支持通配符 |
| `--mode` | `router` | Zenoh 会话模式：`router` / `client` / `peer` |
| `--connect` | — | 连接端点，可多次指定 |
| `--listen` | — | 监听端点，可多次指定 |
| `--show-depth` | 关闭 | 对深度类 PNG 图像应用伪彩色 |
| `--print-interval` | `1.0` | 非图像话题的打印节流间隔（秒） |
| `--max-text` | `240` | 文本 payload 最大打印字符数 |
| `--window-prefix` | `sensor` | OpenCV 窗口名前缀 |

---

### zenoh_topic_monitor.py — 话题监控器

以表格形式实时显示所有活跃 Zenoh 话题的消息频率、payload 大小及时间戳延迟统计。

#### 基本用法

```powershell
# 默认监控所有话题
python zenoh_topic_monitor.py

# 客户端模式
python zenoh_topic_monitor.py --mode client --connect tcp/127.0.0.1:7447

# 仅监控 MuJoCo 话题，0.5 秒刷新
python zenoh_topic_monitor.py --key "mujoco/**" --interval 0.5

# 按话题名排序
python zenoh_topic_monitor.py --sort name
```

#### 参数列表

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--key` | `**` | 监控的 key 表达式 |
| `--mode` | `router` | Zenoh 会话模式 |
| `--connect` | — | 连接端点 |
| `--listen` | — | 监听端点 |
| `--interval` | `1.0` | 表格刷新间隔（秒） |
| `--window` | `5.0` | 计算 Hz 的滑动窗口时长（秒） |
| `--max-topics` | `50` | 最多显示话题数 |
| `--sort` | `hz` | 排序字段：`hz` / `name` / `last` |
| `--no-clear` | 关闭 | 禁止清屏，保留历史输出 |
| `--show-empty` | 关闭 | 保留窗口内无消息的话题行 |

---
