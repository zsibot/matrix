# Zenoh 2D 包围盒可视化工具使用说明

## 1. 工具用途

`visualize_zenoh_bbox_2d.py` 订阅 UeSim 通过 Zenoh 发布的 Actor 包围盒 JSON，并在固定范围的 XY 俯视图中显示：

- Actor 的二维有向包围框；
- 包围盒中心点；
- Actor 局部 X 正方向（Forward）箭头；
- Actor 名称或消息中的标签；
- 当前主题、消息序号、目标数量和最后一帧数据年龄。

工具只显示每次收到的最新一帧，不累积历史包围盒。因此，目标移动后不应在画面中留下历史轨迹。

本工具适合检查动态目标位置、朝向、尺寸、坐标轴方向以及 Zenoh 数据是否持续更新。它不是相机图像上的 2D 检测框工具，也不执行世界坐标到相机像素坐标的投影。

## 2. 部署文件

MATRiX 发布目录中的文件为：

```text
MATRiX_v1.0.13/
├── Tools/
│   └── visualize_zenoh_bbox_2d.py
└── docs/
    └── ZenohBBox2D_CN.md
```

`visualize_zenoh_bbox_2d.py` 是单文件工具，Zenoh 配置、消息解码、包围盒解析和绘图逻辑均已内置。复制或发布时不依赖 UeSim/MATRiX 中的其他 Python 文件。

## 3. 运行环境

建议使用 Python 3.8 或更高版本。安装依赖：

```bash
python3 -m pip install eclipse-zenoh matplotlib
```

如果系统同时存在多个 Python 环境，应使用实际运行脚本的同一个 Python 安装依赖。

## 4. 快速启动

先启动 UeSim，并确认 Zenoh Router 或 UeSim 内置的 Zenoh 服务正在监听。然后在 MATRiX 目录运行：

```bash
cd /path/to/MATRiX_v1.0.13
python3 Tools/visualize_zenoh_bbox_2d.py
```

默认配置为：

- Zenoh 主题：`rt/dynamicinfo`
- 会话模式：`client`
- Zenoh 地址：`tcp/127.0.0.1:7447`
- 刷新间隔：50 ms
- 窗口尺寸：1280 × 720
- 世界 X 范围：-250 m 到 150 m
- 世界 Y 范围：-50 m 到 50 m

关闭窗口或在终端按 `Ctrl+C` 可退出。

查看完整命令行参数：

```bash
python3 Tools/visualize_zenoh_bbox_2d.py --help
```

## 5. 常用命令

### 5.1 连接本机 Zenoh

```bash
python3 Tools/visualize_zenoh_bbox_2d.py \
  --connect tcp/127.0.0.1:7447
```

`client` 模式下，如果没有指定 `--connect` 或 `--listen`，程序会自动连接 `tcp/127.0.0.1:7447`。

### 5.2 连接远程 UeSim 主机

```bash
python3 Tools/visualize_zenoh_bbox_2d.py \
  --connect tcp/192.168.1.100:7447
```

把 `192.168.1.100` 替换为运行 UeSim 或 Zenoh Router 的主机地址，并确认 7447/TCP 端口可达。

### 5.3 修改订阅主题

```bash
python3 Tools/visualize_zenoh_bbox_2d.py \
  --key rt/dynamicinfo
```

`--key` 接受 Zenoh key expression，也可按实际系统配置指定其他主题。

### 5.4 修改显示范围

```bash
python3 Tools/visualize_zenoh_bbox_2d.py \
  --x-min -100 --x-max 100 \
  --y-min -80 --y-max 80
```

单位均为米。若目标数据正常但窗口为空，应首先检查目标是否位于当前显示范围之外。

### 5.5 修改窗口尺寸和刷新间隔

```bash
python3 Tools/visualize_zenoh_bbox_2d.py \
  --image-width 1920 \
  --image-height 1080 \
  --dpi 120 \
  --interval-ms 33
```

`--interval-ms` 只控制绘图刷新频率，不改变传感器或发布端的消息频率。程序始终绘制收到的最新一帧。

### 5.6 作为 Zenoh Router 监听

```bash
python3 Tools/visualize_zenoh_bbox_2d.py \
  --mode router \
  --listen tcp/0.0.0.0:7447
```

一般情况下使用默认 `client` 模式即可。只有确认本程序需要承担 Router 角色时才使用该方式，同时应避免与已有服务占用同一端口。

`--connect` 和 `--listen` 均可重复指定，以配置多个端点。

## 6. 坐标系定义

UeSim 发布的包围盒已经转换到 ROS FLU 世界坐标系，长度单位为米：

| 轴 | 正方向 | 二维窗口中的含义 |
|---|---|---|
| X | Forward，前 | 水平坐标轴 |
| Y | Left，左 | 垂直坐标轴 |
| Z | Up，上 | 2D 俯视图不显示高度 |

包围盒局部坐标也采用 FLU：

- 局部 `+X`：Actor 前方；
- 局部 `+Y`：Actor 左方；
- 局部 `+Z`：Actor 上方；
- `forward`：局部 `+X` 在 ROS 世界坐标中的单位方向；
- 二维局部左方向由 `(-forward.y, forward.x)` 计算。

UeSim 内部使用厘米和 Y 向右的坐标约定。`Actor BBox To JSON String` 在发布前已经完成：

```text
ROS.x =  UE.x × 0.01
ROS.y = -UE.y × 0.01
ROS.z =  UE.z × 0.01
```

因此接收脚本不要再次乘以 0.01，也不要再次对 Y 取反。否则会出现尺寸缩小 100 倍或左右镜像。

## 7. JSON 消息格式

单个包围盒的标准字段如下：

| 字段 | 是否必需 | 含义 |
|---|---:|---|
| `coordinate_system` | 否 | UeSim 输出为 `ROS` |
| `unit` | 否 | UeSim 输出为 `m` |
| `center` | 是 | ROS 世界坐标中的中心点，单位 m |
| `extent` | 是 | 沿局部前、左、上三个轴的半尺寸，单位 m |
| `size` | 否 | 完整尺寸；缺省时由 `extent × 2` 计算 |
| `rotation` | 否 | ROS FLU 中的 pitch、yaw、roll，单位为度 |
| `forward` | 是 | Actor 前方向量；程序会将非零向量归一化 |
| `corners` | 是 | 8 个 ROS 世界坐标角点，每个角点包含 x/y/z |
| `label` / `name` / `id` | 否 | 显示名称，按该顺序选取 |

标准单目标示例：

```json
{
  "coordinate_system": "ROS",
  "unit": "m",
  "center": {"x": 10.0, "y": 2.0, "z": 0.75},
  "extent": {"x": 2.0, "y": 1.0, "z": 0.75},
  "size": {"x": 4.0, "y": 2.0, "z": 1.5},
  "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
  "forward": {"x": 1.0, "y": 0.0, "z": 0.0},
  "corners": [
    {"x": 8.0, "y": 1.0, "z": 0.0},
    {"x": 12.0, "y": 1.0, "z": 0.0},
    {"x": 12.0, "y": 3.0, "z": 0.0},
    {"x": 8.0, "y": 3.0, "z": 0.0},
    {"x": 8.0, "y": 1.0, "z": 1.5},
    {"x": 12.0, "y": 1.0, "z": 1.5},
    {"x": 12.0, "y": 3.0, "z": 1.5},
    {"x": 8.0, "y": 3.0, "z": 1.5}
  ],
  "label": "vehicle_1"
}
```

二维矩形使用 `center`、`extent.x`、`extent.y` 和 `forward` 计算。`corners` 虽然不参与二维轮廓计算，但共用解析器仍要求它恰好包含 8 个有效角点，以保证消息格式完整，并与 3D 工具兼容。

## 8. 支持的消息封装形式

程序支持以下形式：

1. 直接发送单个包围盒对象；
2. 发送包围盒数组；
3. 使用 `bbox`、`bboxes`、`objects`、`actors`、`dynamicinfo` 或 `data` 作为外层字段；
4. 使用 Actor ID 作为外层 key；
5. 外层 Actor ID 对应的 value 是再次 JSON 编码后的字符串。

UeSim 当前常见的多目标双重编码形式如下：

```json
{
  "BP_Simple_Sedan26": "{\"center\":{...},\"extent\":{...},\"forward\":{...},\"corners\":[...]}"
}
```

上例中的 `...` 只用于说明封装层次，不是可直接发布的完整 JSON。解析器会解码内部字符串；若内部对象没有 `label`、`name` 或 `id`，会把外层 Actor ID 用作显示标签。

## 9. 显示内容的判断方法

- 彩色半透明矩形：Actor 在世界 XY 平面内的有向包围盒；
- 圆点：包围盒中心；
- 箭头：`forward` 指示的局部 +X 方向；
- 文本：消息中的标签或外层 Actor ID；
- `message`：成功解析的消息序号；
- `boxes`：当前最新消息内的有效包围盒数量；
- `age`：当前显示帧距离接收时刻的时间。

若 `age` 持续增长，表示窗口仍在刷新，但没有收到新的有效消息。若 `message` 增长而目标不移动，应检查发布端是否一直在发送相同坐标。

## 10. 常见问题

### 10.1 窗口一直显示 Waiting for bbox data

依次检查：

1. UeSim 是否已经开始发布动态目标信息；
2. 主题是否确实为 `rt/dynamicinfo`；
3. Zenoh 地址和端口是否正确；
4. 远程主机防火墙是否允许 7447/TCP；
5. Router、发布端和本程序的 Zenoh 配置是否能互相发现或连接。

### 10.2 终端输出 Ignored invalid bbox payload

消息能够到达，但格式未通过解析。常见原因包括：

- `center`、`extent` 或 `forward` 缺少 x/y/z；
- 数值不是有限数；
- `corners` 不是数组或不是恰好 8 个角点；
- JSON 双重编码不完整；
- 主题中混入了其他类型的消息。

### 10.3 有消息但画面中没有目标

检查 `center.x`、`center.y` 是否在 `--x-min/--x-max` 和 `--y-min/--y-max` 范围内。可以临时扩大范围确认数据位置。

### 10.4 目标左右镜像或方向相反

本工具假设输入已经是 ROS FLU，不再转换坐标。如果发布端发送的是原始 Unreal 坐标，必须在发布端或适配层进行厘米到米以及 Y 轴取反的转换，不应修改本工具的固定 ROS 解释。

### 10.5 无法打开图形窗口

Matplotlib 需要可用的桌面图形环境。在 SSH 环境中需要启用 X11 转发或使用远程桌面；纯无头服务器无法直接显示交互窗口。

## 11. 与 3D 工具的区别

项目中的 `visualize_zenoh_bbox.py` 是另一个独立的三维查看器，它使用消息中的 8 个角点绘制完整 3D 包围盒，并自动调整坐标范围。运行 2D 工具不需要该文件。

`visualize_zenoh_bbox_2d.py` 采用固定范围的 XY 俯视图，适合同时观察大量目标的位置和朝向。它忽略 Z 高度对轮廓的影响，并使用 `extent` 和 `forward` 重建二维矩形。
