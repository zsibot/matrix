# MATRiX v1.1.1 release notes

[README](../README.md) | [中文](Release_Notes_CN.md)

Updated on 2026-09-21 against the Linux x86_64 files packaged on 2026-09-21 at 15:08 China Standard Time, bundled configuration and schemes, and embedded-controller provenance. Unpackaged changes in the development source tree are not automatically features of this binary.

## Package and tool updates

- Default robot: `xgw2`. The portable model path is `Content/model/xgw2/xgw2.xml`, relative to the `UeSim/` project directory.
- Defaults remain `inside_mc=true`, `network_mode=standalone`, and `sensor_sync_mode=true`. The active configuration contains six sensors matching `config_default.json`: IMU, odometry, GPS, RGB, depth, and Airy. Synchronized scheduling is enabled. Enter the simulation and spawn the robot before receiving data; load and apply other schemes when needed.
- Included schemes cover RGB, depth, infrared, fisheye, panorama, gimbal, IMU, odometry, GPS, Airy, and MID360. `config_data.json` uses MID360. Airy/MID360 use a shared `backend` configuration field; verify the actual CPU/GPU backend in logs.
- Bundled provenance records the 2026-09-08 controller 0.6.6 integration, including XXG gait updates, XG2 Passive behavior and XGW2 stand-up wheel locking. Included weights are not evidence that every policy is integrated; see [motion control](Motion_Control.md).
- Perspective projection now filters invalid high-order distortion branches. Four-view fisheye projection includes optional world-space bbox overlays.
- `visualize_zenoh_bbox.py` is now a categorized XY view with velocity and actor details. `_2d.py` retains the older fixed-range view.
- Raw Zenoh recording, offline preview and replay tools are included with their helper modules.
- This rebuild includes `config_semantic.json` and `config_rgb_semantic.json` for semantic-only and aligned RGB/semantic capture. Semantic output is a lossless class-ID PNG that the receiver can colorize. Semantic cameras are optional schemes, not part of the default six-sensor configuration.
- The launcher handles spaces and symlinks, reports a missing binary, preserves arguments and forwards the process exit status. The spawn sender defaults to localhost.
- A Python dependency file, tool index, and revised bilingual setup instructions are provided.

## Migration

Use the complete v1.1.1 runtime, Engine, models and plugins together. Back up old configuration and migrate fields selectively. Do not overwrite the new configuration directory wholesale. Model paths should remain portable; retain the selected embedded/external controller mode.

The default six-sensor configuration supports camera/LiDAR checks. Apply a semantic or surround scheme explicitly before using those viewers. The historical filename `config_v1.0.12_zgwt.json` is retained intentionally.

Update the map catalog and install DLCs matching this release. Verify old-map compatibility with the map distributor. Optional external `robot_mc` is still a separate download whose own README determines its requirements and robot types.

Install [tool dependencies](../Tools/README.md) and keep the helper modules with their entry scripts.

## Validation boundary

Offline `--help` and `--check-only` validate CLI interfaces and configuration, not live GPU operation, map loading, network throughput or robot behavior. This documentation/tool update does not rebuild or replace the simulator binary. Verify the full runtime on the target machine.

Offline checks passed for 12 CLI help entry points, default/MID360/four-view fisheye calibration, 30 receiver/bbox/recording regression tests, relative documentation links and configuration JSON. A stub runtime verified launcher paths, symlinks, argument forwarding and exit status; the real GPU simulator was not launched.

Rebuild ID: `20260921T070837079667Z-fd3f20ec` (2026-09-21 15:08 China Standard Time). XGW2 XML/URDF, body and mesh resources were updated; semantic/RGB presets are included and the default six-sensor configuration is restored. Replace all previous v1.1.1 parts and checksum files together; do not mix builds.
