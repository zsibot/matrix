# Architecture and Maintainer Guide

[README](../README.md) | [Contributing](../CONTRIBUTING.md)

This guide records the architecture that can be verified in the current `uesim` source tree. It intentionally avoids release-package layouts and helper scripts that are not present in source.

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
6. Installed DLCs are discovered from `Saved/DLCs` and `Content/DLCs`. A packaged UI may additionally call the runtime load/open functions.
7. Motion control starts only for the selected and configured control mode.

Changes to spawn order need regression tests for sensor attachment, body-to-geom transforms, transport startup, and controller initialization.

## Configuration contract

The current saved schema is rooted at `robot` and includes:

- identity/model: `robot_type`, `mujoco_model`, `main_body`;
- execution: `mujoco_running`, `inside_mc`, `hardware_simulation`;
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

Public documentation currently lists `xgb`, `xg2`, `xgw`, `xgw2`, `zgws`, `zgwt`, and `zgwsarm`. UI/protocol aliases include `xg` for `xgb` and `zgws_arm` for `zgwsarm`.

- All seven documented models support Passive, Stand, and Walk.
- Only `xgb` registers Jump and FrontJump.
- The embedded loop targets 500 Hz and ONNX inference targets 100 Hz.
- The embedded core currently uses local Zenoh `tcp/127.0.0.1:7447` with fixed `mujoco/state` and `mujoco/cmd` keys.
- Linux simulated hardware uses a process-global shared-memory path and should be limited to one robot per UeSim process/container.
- Embedded control and external simulated-hardware control must not command the same robot simultaneously.

## DLC and map releases

`MainWorld` is the base map. DLC code recursively scans both supported directories and can mount packages at startup or at runtime.

The Windows bulk packaging script and Linux bulk packaging script are separate sources of release intent and can contain different map lists. Before publishing:

1. compare the intended release manifest with both scripts;
2. package on the target platform;
3. start without DLCs and verify `MainWorld`;
4. mount every shipped `.pak`;
5. enumerate and open every expected map by name;
6. confirm the release documentation lists only assets actually shipped.

Do not publish stable numeric map IDs unless a versioned runtime API explicitly defines them.

## Platform and release checks

Minimum smoke-test matrix:

| Area | Windows | Linux |
|---|---:|---:|
| DX12/Vulkan startup and `MainWorld` | Required | Required |
| Runtime MJCF load | Required | Required |
| Zenoh state/command keys | Required | Required |
| Every sensor family included in release | Required | Required |
| DLC discovery and map opening | Required | Required |
| Embedded motion models included in release | Required | Required |
| Shared-memory simulated hardware | N/A | Required when shipped |
| Pixel Streaming 2 | Required when shipped | Required when shipped |

Also verify that documentation-only repositories do not advertise runtime tools, Docker images, model weights, or web-server bundles unless those artifacts are actually downloadable and versioned.

## Security and repository hygiene

Never commit router credentials, service tokens, private endpoints, licensed engine content, proprietary model weights, or user-specific absolute paths. Security reports follow [SECURITY.md](../SECURITY.md), not public issues.
