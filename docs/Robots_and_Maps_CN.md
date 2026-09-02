# 机器人与地图

[中文主页](README_CN.md) | [English](Robots_and_Maps.md)

本文说明 MATRiX v1.0.13 Linux 运行包。地图 DLC 必须与该版本及其 Unreal Engine 构建匹配。

## 机器人模型

| 模型标识 | MJCF 资产 | 内置运控 | 说明 |
|---|---:|---:|---|
| `go2` | 有 | 无 | Unitree Go2 模型 |
| `go2w` | 有 | 无 | Go2 轮式版本 |
| `xgb` | 有 | 有 | UI/协议中可能显示为 `xg`；支持跳跃动作 |
| `xg2` | 有 | 有 | 第二代 XG 四足模型 |
| `xgw` | 有 | 有 | XG 轮足版本 |
| `xgw2` | 有 | 有 | 第二代 XG 轮足模型 |
| `xxg` | 有 | 有 | 带头部关节的 XXG 四足模型 |
| `zgws` | 有 | 有 | 支持 Passive / Stand / Walk |
| `zgwt` | 有 | 有 | 支持 Passive / Stand / Walk |
| `zgwsarm` | 有 | 有 | UI 中可能显示为 `zgws_arm` |

模型标识需要与模型目录及 `mujoco_model` 指向的 MJCF 匹配。v1.0.13 为 `xgb`、`xg2`、`xgw`、`xgw2`、`xxg`、`zgws`、`zgwt` 和 `zgwsarm` 注册了内置运控。`go2`、`go2w` 是仿真模型，不在当前内置运控列表中。

### 机器人预览

<table>
  <tr>
    <td align="center"><img src="../demo_gif/Robot/zsl-1.png" alt="xgb 机器人" width="280"/><br/><code>xgb</code></td>
    <td align="center"><img src="../demo_gif/Robot/zsl-1w.png" alt="xgw 机器人" width="280"/><br/><code>xgw</code></td>
  </tr>
  <tr>
    <td align="center"><img src="../demo_gif/Robot/zsm-1w.png" alt="zgws 机器人" width="280"/><br/><code>zgws</code></td>
    <td align="center"><img src="../demo_gif/Robot/go2.png" alt="go2 机器人" width="280"/><br/><code>go2</code></td>
  </tr>
  <tr>
    <td align="center"><img src="../demo_gif/Robot/go2w.png" alt="go2w 机器人" width="280"/><br/><code>go2w</code></td>
    <td></td>
  </tr>
</table>
## 动态地图列表

开源基础包的 `UeSim/Content/model/MapDataTable.json` 初始为空，这是正常状态。进入地图选择界面后：

1. 点击 **UPDATE LIST（更新列表）** 获取当前地图目录；
2. 点击目标地图下方的 **DOWNLOAD（下载）**；
3. 等待 DLC 下载和挂载完成；
4. 地图卡片显示可进入后再选择地图。

当前目录是 v1.0.13 可用地图的依据。不要继续使用旧数字地图 ID，也不要混用其他版本的目录。

## DLC 目录与加载行为

手动安装时，从[百度网盘（提取码：`6sth`）](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F)下载对应 DLC，解压 `.pak` 后放入推荐目录：

```text
UeSim/Saved/DLCs/*.pak
```

运行时也扫描 `UeSim/Content/DLCs/*.pak`。手动安装后重启 UeSim。只有 `.pak`、但当前地图列表中没有匹配条目时，程序可能已挂载地图但界面不显示卡片。

完整流程见[地图与 DLC](Map_DLC_CN.md)。

## 地图预览

<table>
  <tr>
    <td><img src="../demo_gif/Maps/TOWN10.png" alt="Town10World" width="280"/><br/><code>Town10World</code></td>
    <td><img src="../demo_gif/Maps/VENICE.png" alt="VeniceWorld" width="280"/><br/><code>VeniceWorld</code></td>
  </tr>
  <tr>
    <td><img src="../demo_gif/Maps/YARD.png" alt="YardWorld" width="280"/><br/><code>YardWorld</code></td>
    <td><img src="../demo_gif/Maps/CROWD.png" alt="CrowdWorld" width="280"/><br/><code>CrowdWorld</code></td>
  </tr>
  <tr>
    <td><img src="../demo_gif/Maps/HOUSE.png" alt="HouseWorld" width="280"/><br/><code>HouseWorld</code></td>
    <td><img src="../demo_gif/Maps/OFFICE.png" alt="OfficeWorld" width="280"/><br/><code>OfficeWorld</code></td>
  </tr>
  <tr>
    <td><img src="../demo_gif/Maps/IROSFLAT2025.png" alt="IROSFlatWorld2025" width="280"/><br/><code>IROSFlatWorld2025</code></td>
    <td><img src="../demo_gif/Maps/IROSSLOP2025.png" alt="IROSSloppedWorld2025" width="280"/><br/><code>IROSSloppedWorld2025</code></td>
  </tr>
  <tr>
    <td><img src="../demo_gif/Maps/3DGS.png" alt="3DGSWorld" width="280"/><br/><code>3DGSWorld</code></td>
    <td><img src="../demo_gif/Maps/Moon.png" alt="MoonWorld" width="280"/><br/><code>MoonWorld</code></td>
  </tr>
</table>
