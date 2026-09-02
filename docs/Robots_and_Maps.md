# Robots and Maps

[README](../README.md) | [中文](Robots_and_Maps_CN.md)

This page describes the MATRiX v1.0.13 Linux release. DLCs must match this release and its Unreal Engine build.

## Robot models

| Model key | MJCF assets | Embedded motion core | Notes |
|---|---:|---:|---|
| `go2` | Yes | No | Unitree Go2 model |
| `go2w` | Yes | No | Wheeled Go2 variant |
| `xgb` | Yes | Yes | UI/protocol label may appear as `xg`; supports jump actions |
| `xg2` | Yes | Yes | Second XG quadruped |
| `xgw` | Yes | Yes | Wheeled XG variant |
| `xgw2` | Yes | Yes | Second wheeled XG variant |
| `xxg` | Yes | Yes | XXG quadruped with head joints |
| `zgws` | Yes | Yes | Embedded Passive / Stand / Walk |
| `zgwt` | Yes | Yes | Embedded Passive / Stand / Walk |
| `zgwsarm` | Yes | Yes | UI label may appear as `zgws_arm` |

The model key must match the model directory and MJCF selected by `mujoco_model`. The embedded controller is registered for `xgb`, `xg2`, `xgw`, `xgw2`, `xxg`, `zgws`, `zgwt`, and `zgwsarm`. `go2` and `go2w` are simulation assets without a v1.0.13 built-in motion core.

### Robot previews

<table>
  <tr>
    <td align="center"><img src="../demo_gif/Robot/zsl-1.png" alt="xgb robot" width="280"/><br/><code>xgb</code></td>
    <td align="center"><img src="../demo_gif/Robot/zsl-1w.png" alt="xgw robot" width="280"/><br/><code>xgw</code></td>
  </tr>
  <tr>
    <td align="center"><img src="../demo_gif/Robot/zsm-1w.png" alt="zgws robot" width="280"/><br/><code>zgws</code></td>
    <td align="center"><img src="../demo_gif/Robot/go2.png" alt="go2 robot" width="280"/><br/><code>go2</code></td>
  </tr>
  <tr>
    <td align="center"><img src="../demo_gif/Robot/go2w.png" alt="go2w robot" width="280"/><br/><code>go2w</code></td>
    <td></td>
  </tr>
</table>
## Dynamic map catalog

The open base package intentionally starts with an empty `UeSim/Content/model/MapDataTable.json`. On the map-selection screen:

1. select **UPDATE LIST** to retrieve the current catalog;
2. select **DOWNLOAD** below the required map;
3. wait for the DLC download and mount to complete;
4. enter the map when its card is marked ready.

The catalog is the source of truth for the maps currently offered for v1.0.13. Do not rely on old numeric IDs or copy a catalog from another release.

## DLC locations and loading

For manual installation, download the required DLC from the [Baidu Netdisk mirror (code: `6sth`)](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F), extract the `.pak`, and place it in the preferred directory:

```text
UeSim/Saved/DLCs/*.pak
```

The runtime also scans `UeSim/Content/DLCs/*.pak`. Restart UeSim after manual installation. A `.pak` without a matching current catalog entry may be mounted but not shown as a card.

See [Map_DLC.md](Map_DLC.md) for the complete automatic and manual workflow.

## Map previews

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
