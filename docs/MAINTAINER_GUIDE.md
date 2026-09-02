# Architecture and Maintainer Guide

[README](../README.md) | [Contributing](../CONTRIBUTING.md)

This guide records the v1.0.13 Linux release boundary and the corresponding `uesim` source architecture reviewed at commit `b666c0d9`.

## Runtime architecture

| Component | Responsibility |
|---|---|
| `UeSim` runtime module | Application/game integration, launch flow, default world, robot spawning, and DLC-facing runtime functions |
| MuJoCo importer plugin | Runtime MJCF/XML loading, MuJoCo stepping, generated visuals, and coordinate conversion |
| `RobotSensorSimulation` | Camera, LiDAR, IMU, GPS, and odometry simulation; timestamping; ROS 2-compatible CDR serialization over Zenoh |
| `MyProjectRobotZenohPlugin` | Robot state and command transport through Zenoh |
| `MatrixMotionControl` | Embedded motion cores, ONNX inference, logical gamepad/UDP input, and Linux simulated-hardware integration |
| `LanSync` | Optional LAN state and event synchronization |
| DLC game-instance code | `.pak` discovery/mounting, available-map enumeration, and map opening |
| Pixel Streaming 2 | Unreal browser-streaming integration; signalling/web server remains a separate process |

Other enabled plugins, including task, procedural world, and Gaussian-splatting integrations, should be documented only when their source contract and packaged assets are part of a release.

## Startup flow

1. Unreal starts in `/Game/Maps/MainWorld.MainWorld` unless another map is selected.
2. The launcher/game layer loads `Content/model/config/config.json`.
3. The selected MJCF is loaded and converted into the Unreal representation.
4. Sensors are created from the dynamic `robot.sensors` object.
5. The MuJoCo worker advances physics; transport and sensors publish from their own scheduling paths.
6. The map UI loads `Content/model/MapDataTable.json`; the base release starts with an empty catalog and can download a validated replacement.
7. Installed DLCs are discovered from `Saved/DLCs` and `Content/DLCs`; the UI can download, mount, and open a selected catalog entry.
8. Motion control starts only for the selected and configured control mode.

Changes to spawn order need regression tests for sensor attachment, body-to-geom transforms, transport startup, and controller initialization.

## Configuration contract

The current saved schema is rooted at `robot` and includes:

- identity/model: `mujoco_model`, `main_body`, `weapon`;
- execution: `mujoco_running`, `inside_mc`;
- networking: `network_mode`, `zenoh_router`, `state_port`, `cmd_port`;
- timing: robot-level `sensor_sync_mode`;
- pose: `position`;
- sensors: dynamic `sensors` object.

Despite their historical names, `state_port` and `cmd_port` are string Zenoh keys. Current defaults are `mujoco/state` and `mujoco/cmd`.

Do not reintroduce legacy fields such as `EgoView`, `synchronous_mode`, `synchronous_frequency`, per-sensor `synchronized`, `sensor_master_rate_hz`, or `sensor_overrun_policy`. The current save path removes or ignores those compatibility fields.

When adding a configuration field:

1. add a default and load behavior;
2. preserve unknown sensor JSON when round-tripping;
3. update the launcher/editor binding;
4. define its saved type and migration behavior;
5. update both the English README summary and the relevant guide;
6. test loading an older configuration and saving it again.

## Physics, transforms, and timing

The MuJoCo worker targets 500 Hz by default. This is a target, not a guarantee under load.

The default transform convention is:

```text
MuJoCo metres, right-handed (x, y, z)
    -> Unreal units, left-handed (x, -y, z)
    -> default scale ×100
```

Sensors attached to generated visual geometry require the body-to-geom compensation used by the standard spawn flow. A direct mesh attachment that omits this transform can appear correct at the root pose but drift or rotate incorrectly during motion.

All current sensors use the unified robot clock:

| Producer | Default target boundary |
|---|---:|
| IMU and robot state | 500 Hz / 2 ms |
| GPS and odometry | 100 Hz / 10 ms |
| Cameras and LiDAR | 10 Hz / 100 ms |

Asynchronous scheduling uses absolute deadlines. On overrun it records actual acquisition time and re-anchors instead of publishing a burst of catch-up samples. Synchronous mode is a robot-level switch and schedules frequency groups. Changes to timestamping must be checked across every sensor family, not only cameras.

## Sensor contract

Current families are RGB, infrared, depth, panorama RGB, fisheye, generic LiDAR, Mid-360, Airy, IMU, GPS, and odometry.

The maintained templates under `Content/model/config/sensors` are the source of truth for field names and example defaults. Legacy `wargb` and `wadepth` types have been replaced by `fisheye`, and the current template set does not define `panoramadepth`.

Sensor payloads use ROS 2-compatible CDR encodings over Zenoh. Keep `frame_id` / `child_frame_id`, acquisition timestamps, image/depth encoding, and point-cloud layout stable when changing implementations.

## Motion-control contract

Public documentation lists `xgb`, `xg2`, `xgw`, `xgw2`, `xxg`, `zgws`, `zgwt`, and `zgwsarm`. UI/protocol aliases include `xg` for `xgb` and `zgws_arm` for `zgwsarm`.

- All eight documented models have a built-in motion core; available actions must be queried per model.
- Only `xgb` registers Jump and FrontJump.
- The embedded loop targets 500 Hz and ONNX inference targets 100 Hz.
- MuJoCo simulated hardware implements the original controller shared-memory ABI.
- Built-in motion control connects to that ABI when `inside_mc=true`; an external controller uses it when `inside_mc=false`.
- The shared-memory path is process-global and should be limited to one matching controller per robot runtime.
- Built-in and external control must never command the same robot simultaneously.

## DLC and map releases

The public base package intentionally ships an empty `Content/model/MapDataTable.json`. The map UI updates that catalog, downloads a selected DLC, and refreshes installed-map state. DLC code recursively scans both supported directories and can mount packages at startup or at runtime.

Before publishing a Linux release:

1. compare the intended release manifest with the Linux packaging output;
2. start without DLCs and verify the empty catalog state;
3. update `MapDataTable.json` through the UI;
4. automatically download and mount a catalog DLC;
5. manually install a `.pak` under `UeSim/Saved/DLCs` and restart;
6. enumerate and open every expected map by name;
7. confirm the release documentation lists only downloadable assets.

Do not publish stable numeric map IDs unless a versioned runtime API explicitly defines them.

## Platform and release checks

Minimum Linux smoke-test matrix:

| Area | Requirement |
|---|---:|
| Vulkan startup and default scene | Required |
| Runtime MJCF load | Required |
| Zenoh state/command keys | Required |
| Every sensor family included in release | Required |
| Map-list update, DLC download, discovery, and opening | Required |
| Embedded motion models included in release | Required |
| Optional external shared-memory control | Required when documented |
| Pixel Streaming 2 | Required when shipped |

Also verify that documentation-only repositories do not advertise runtime tools, Docker images, model weights, or web-server bundles unless those artifacts are actually downloadable and versioned.

## Security and repository hygiene

Never commit router credentials, service tokens, private endpoints, licensed engine content, proprietary model weights, or user-specific absolute paths. Security reports follow [SECURITY.md](../SECURITY.md), not public issues.
