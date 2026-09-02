# MATRiX v1.0.13 motion control

[Back to README](../README.md) | [中文](Motion_Control_CN.md)

The open v1.0.13 release uses built-in motion control by default. The external `robot_mc` runtime is not distributed in this package and must be downloaded separately when needed.

## Default built-in mode

The active configuration is `UeSim/Content/model/config/config.json`, with:

```json
"inside_mc": true
```

UeSim starts both simulated hardware and the embedded controller. No separate controller terminal or dependency installation is required.

```bash
./UeSim.sh
```

Check the current value with:

```bash
rg -n '"inside_mc"' UeSim/Content/model/config/config.json
```

Restart UeSim after manually changing the mode.

Built-in controller IDs registered by the current source are:

```text
xgb  xg2  xgw  xgw2  xxg  zgws  zgwt  zgwsarm
```

`go2` and `go2w` simulation assets are present but are not in the current embedded-controller list.

## Gamepad and UDP input

The default `Auto` input mode gives recent UDP packets priority and otherwise reads the hardware gamepad. Linux uses `/dev/input/js0` by default. Common Xbox controls are left stick for translation, right-stick X for yaw, `LB+Y` to stand, `LB+B` for balance stand, `LB+X` for joint hold, and `LB+RB` for passive mode.

UDP examples require only Python's standard library:

```bash
python3 Tools/matrix_mc_udp_test.py stand
python3 Tools/matrix_mc_udp_test.py walk --stand-first --forward 0.25 --duration 3
python3 Tools/matrix_mc_udp_test.py rotate --yaw 0.25 --duration 2
python3 Tools/matrix_mc_udp_test.py passive
```

Use `--host <SIMULATOR_IP>` for a remote simulator. UDP input listens on port 7447 by default and expires after 0.5 seconds without a valid packet.

## Optional external robot_mc (separate download)

This release contains no external controller binary, model bundle, dependencies, or installer. Download the Linux x86_64 runtime asset from:

<https://github.com/GENISOM-AI/MATRiX_Robot_MC/releases>

The external controller and its dependency installer require Ubuntu 22.04 x86_64. This restriction applies only to the optional external controller, not to the UeSim simulator itself.

Do not use GitHub's automatically generated source archives; they do not contain the complete runtime.

Extract it outside the MATRiX directory, then follow that release's README:

```bash
chmod +x install_deps.sh run_mc.sh
./install_deps.sh
```

The installer may use sudo, APT, network access, and bundled packages. The external v0.6.4 README checked for this release declares these mappings:

| UeSim model | External project model | `ROBOT_TYPE` |
|---|---|---|
| `xgb` | `zsl-1` / `zsl-2` | `XG` |
| `xgw` | `zsl-1w` | `XGW` |
| `xgw2` | `zsl-2w` | `XGW2` |
| `zgws` / `zgwt` | `zsm-1w` | `ZGWS` |
| `zgwsarm` | `zgwsarm` | `ZGWS_ARM` |

`xg2` and `xxg` are supported by v1.0.13 built-in control but are not listed by the public external v0.6.4 README; do not invent a `ROBOT_TYPE` for them. The external project's supported list and launcher interface may change, so its downloaded README is authoritative.

Stop UeSim and edit `UeSim/Content/model/config/config.json`:

```json
"inside_mc": false
```

Save the file and start the simulator with `./UeSim.sh`.

After entering the simulation scene, start `./run_mc.sh r` from the separately extracted controller directory. Never run the embedded and external controllers together.

To restore the release default, stop the external controller and UeSim, then change the configuration back to:

```json
"inside_mc": true
```

Restart with `./UeSim.sh`.

The runtime log is `UeSim/Saved/Logs/UeSim.log`.
