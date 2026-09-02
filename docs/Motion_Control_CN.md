# MATRiX v1.0.13 运动控制指南

[返回中文主页](README_CN.md) | [English](Motion_Control.md)

v1.0.13 开源发布包默认只使用内置运控。独立 `robot_mc` 不随包分发，需要时由用户自行下载。

## 1. 默认模式

主配置：

```text
UeSim/Content/model/config/config.json
```

默认值：

```json
"inside_mc": true
```

此时 UeSim 同时启动模拟硬件和内置控制器。不要另外启动独立控制器。

```bash
./UeSim.sh
```

可用以下命令确认当前值：

```bash
rg -n '"inside_mc"' UeSim/Content/model/config/config.json
```

手动修改模式后必须重启 UeSim。

## 2. 内置运控

当前源码注册的内置运控机型：

```text
xgb  xg2  xgw  xgw2  xxg  zgws  zgwt  zgwsarm
```

`go2`、`go2w` 可作为仿真模型使用，但不在当前内置运控列表中。内置策略资源位于：

```text
UeSim/Plugins/MatrixMotionControl/
```

运行日志：

```text
UeSim/Saved/Logs/UeSim.log
```

检查运控状态：

```bash
rg 'MatrixMotionControl|embedded motion|inside_mc' UeSim/Saved/Logs/UeSim.log
```

## 3. 手柄与 UDP

默认输入模式为 `Auto`：最近收到的 UDP 输入优先，否则读取硬件手柄。Linux 默认读取 `/dev/input/js0`。

| 输入 | 动作 |
|---|---|
| 左摇杆 | 前后、横移 |
| 右摇杆左右 | 转向 |
| `LB + Y` | 起身/站立 |
| `LB + B` | 平衡站立 |
| `LB + X` | 关节保持 |
| `LB + RB` | 被动模式/停止力矩 |
| `RB + X` | 原地跳跃，取决于机型策略 |
| `RB + Y` | 前跳，取决于机型策略 |

检查手柄：

```bash
ls -l /dev/input/js0
test -r /dev/input/js0 && echo 'gamepad ready'
```

UDP 示例只使用 Python 标准库：

```bash
python3 Tools/matrix_mc_udp_test.py stand
python3 Tools/matrix_mc_udp_test.py walk --stand-first --forward 0.25 --duration 3
python3 Tools/matrix_mc_udp_test.py rotate --yaw 0.25 --duration 2
python3 Tools/matrix_mc_udp_test.py passive
```

远程控制：

```bash
python3 Tools/matrix_mc_udp_test.py --host <仿真器IP> stand
```

内置运控默认监听 UDP `0.0.0.0:7447`。速度输入超过 0.5 秒未刷新会失效；UDP 没有执行确认，请同时观察仿真画面和日志。

## 4. 可选独立 robot_mc（需另行下载）

本发布包不包含独立运控。需要独立进程时，从开源项目的 Releases 下载 Linux x86_64 **runtime asset**：

<https://github.com/GENISOM-AI/MATRiX_Robot_MC/releases>

独立运控的运行和依赖安装环境限定为 Ubuntu 22.04 x86_64。该限制只针对独立运控，不是 UeSim 仿真器本体的系统限制。

不要下载 GitHub 自动生成的 `Source code (zip)` 或 `Source code (tar.gz)`，它们不包含完整运行环境。

### 4.1 解压并安装依赖

独立运控可放在 MATRiX 目录之外，例如作为同级目录：

```text
workspace/
├── MATRiX_v1.0.13/
└── MATRiX_Robot_MC-v0.6.4-linux-x86_64/
```

进入下载并解压的独立运控目录：

```bash
chmod +x install_deps.sh run_mc.sh
./install_deps.sh
```

安装脚本会使用 `sudo`、APT、网络及其自带的 `deps/` 软件包。执行前应先阅读脚本。

### 4.2 配置机型

编辑下载目录中的 `run_mc.sh`：

```bash
export ROBOT_TYPE=XG
```

随本次发布核对的独立运控 v0.6.4 README 声明以下类型：

| UeSim 模型 | 独立项目机型 | `ROBOT_TYPE` |
|---|---|---|
| `xgb` | `zsl-1` / `zsl-2` | `XG` |
| `xgw` | `zsl-1w` | `XGW` |
| `xgw2` | `zsl-2w` | `XGW2` |
| `zgws` / `zgwt` | `zsm-1w` | `ZGWS` |
| `zgwsarm` | `zgwsarm` | `ZGWS_ARM` |

值区分大小写。`xg2`、`xxg` 虽可使用 v1.0.13 内置运控，但不在 v0.6.4 外部项目公开的支持表中，不要自行推测 `ROBOT_TYPE`。独立项目的新版本可能调整支持列表和启动参数，始终以实际下载版本的 README 为准。

### 4.3 切换并启动

先关闭 UeSim，然后编辑：

```text
UeSim/Content/model/config/config.json
```

将下面字段改为 `false`：

```json
"inside_mc": false
```

保存后启动仿真器：

```bash
./UeSim.sh
```

等待 UeSim 进入场景并创建模拟硬件，再在第二个终端进入下载的运控目录：

```bash
./run_mc.sh r
```

如果独立启动脚本无法选择本地网卡，可按该版本 README 指定控制计算机的物理网卡 IPv4，例如：

```bash
SDK_CLIENT_IP=192.168.1.20 ./run_mc.sh r
```

不要填机器人 IP。独立运行时必须满足：

- `inside_mc=false`；
- UeSim 先启动，独立运控后启动；
- `ROBOT_TYPE` 与仿真模型一致；
- 不存在第二个独立控制器；
- 严格遵守下载版本的物理机器人安全说明。

### 4.4 恢复默认内置运控

先停止独立控制器并退出 UeSim，将配置改回：

```json
"inside_mc": true
```

然后重新运行 `./UeSim.sh`。

## 5. 排查

内置运控未启动时，检查 `inside_mc=true`、机型是否受支持，以及日志中的资源缺失或机器人类型错误。

独立运控无状态时，依次检查启动顺序、模式、机型、独立项目版本和其运行依赖。MATRiX 发布包不维护外部项目内部文件，外部参数以其对应 Release 文档为准。
