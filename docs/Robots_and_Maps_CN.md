# 机器人与地图

[中文主页](README_CN.md) | [English](Robots_and_Maps.md)

本文依据当前 `uesim` 源码整理。发布包可能只包含源码资产的一部分；地图 DLC 必须与目标平台和发布版本匹配。

## 机器人模型

| 模型标识 | MJCF 资产 | 内置运控 | 说明 |
|---|---:|---:|---|
| `go2` | 有 | 无 | Unitree Go2 模型 |
| `go2w` | 有 | 无 | Go2 轮式版本 |
| `xgb` | 有 | 有 | UI/协议中可能显示为 `xg`；支持跳跃动作 |
| `xg2` | 有 | 有 | 第二代 XG 四足模型 |
| `xgw` | 有 | 有 | XG 轮足版本 |
| `xgw2` | 有 | 有 | 第二代 XG 轮足模型 |
| `zgws` | 有 | 有 | 支持 Passive / Stand / Walk |
| `zgwt` | 有 | 有 | 支持 Passive / Stand / Walk |
| `zgwsarm` | 有 | 有 | UI 中可能显示为 `zgws_arm` |

模型标识需要与模型目录及 `mujoco_model` 指向的 MJCF 匹配。公开文档列出的 7 类内置运控模型均支持 Passive、Stand 和 Walk；Jump 与 FrontJump 目前只在 `xgb` 中实现。

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
## 源码打包列表中的地图

`MainWorld` 是基础和默认地图。Windows 批量打包脚本当前列出以下 DLC 地图：

| 分类 | 地图名称 |
|---|---|
| 重建与室内 | `3DGSWorld`、`ApartmentWorld`、`HouseWorld`、`House2World`、`MeetRoomWorld`、`OfficeWorld`、`SceneWorld` |
| 城市与户外 | `BatuluWorld`、`CaliWorld`、`Custom2World`、`Town10World`、`VeniceWorld`、`YardWorld`、`ForestWorld` |
| 交互与游戏 | `CrowdWorld`、`RunningWorld`、`Town10Zombie`、`BloodWorld`、`DungeonWorld` |
| 赛事与地形 | `IROSFlatWorld`、`IROSFlatWorld2025`、`IROSSlopedWorld`、`IROSSloppedWorld2025`、`MoonWorld`、`MarsWorld` |

不要再依赖旧文档中的固定数字地图 ID：运行时按资产和地图名称发现、打开地图。Linux 批量打包清单可能与 Windows 不同，公开发布包也可能只提供上述地图的一部分。

运行时还会通过资产注册表发现地图，包括 HELIOS 地图目录。因此，某些构建中可能出现校准室、Home 或 Laboratory 等附加场景，即使它们没有列入上面的批量 DLC 脚本。

## DLC 目录与加载行为

运行时递归扫描：

```text
Saved/DLCs/*.pak
Content/DLCs/*.pak
```

已安装 DLC 会在启动时挂载。游戏实例还实现了运行时加载单个 DLC、枚举可用地图和打开已安装地图的操作。只有当发布包界面没有暴露这些操作或挂载失败时，才需要通过重启刷新。

请使用同平台、兼容 MATRiX 版本构建的 DLC。其他平台或不同引擎版本生成的 `.pak` 可能可以被发现，但无法成功挂载或打开。

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
