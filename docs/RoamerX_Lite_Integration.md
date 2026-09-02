# GENISOM RoamerX Open Integration with MATRiX v1.0.13

[Usage guide](Getting_Started.md) | [Motion control](Motion_Control.md)

> This document covers only the integration boundary exposed by the MATRiX v1.0.13 Linux runtime. RoamerX installation, packages, launch arguments, and navigation tuning remain owned by the `genisom_roamerx_open` project and must be checked against that project's current README.

## 1. Important change from older instructions

The MATRiX v1.0.13 runtime package does **not** contain:

```text
bin/sim_launcher
open_sim_launcher
src/robot_mc/...
```

Commands using those paths belong to an older source-tree/container layout and must not be used with this package. Start this runtime with `UeSim.sh`, and do not assume it automatically exports `ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION`, or RoamerX workspace paths.

## 2. Integration architecture

```text
MATRiX/UeSim
  ├─ motion control: original shared-memory hardware ABI
  └─ sensors: rt/** over Zenoh :7447
                  │
                  ▼
          Zenoh-to-ROS2 bridge
                  │
                  ▼
      ROS2 sensor topics and TF
                  │
                  ▼
      RoamerX navigation + RViz2
```

MATRiX is the simulator and sensor source. A compatible bridge is responsible for exposing the required ROS 2 messages. RoamerX is responsible for localization/SLAM, costmaps, planning, control, and RViz.

## 3. Requirements

- a Linux environment supported by the selected ROS 2 distribution (the examples below use ROS 2 Humble);
- MATRiX v1.0.13 running successfully;
- a Zenoh-to-ROS2 bridge compatible with the current UeSim CDR payloads;
- a built `genisom_roamerx_open` workspace;
- matching ROS domain and RMW configuration for all ROS 2 processes;
- LiDAR, IMU, odometry, robot control, and required TF frames.

The MATRiX open release does not include an external controller or a ROS 2 dependency installer. Install the bridge and its ROS dependencies from the bridge project's instructions. UeSim application keys and ROS 2 DDS/RMW discovery are separate layers.

## 4. Configure the required MATRiX sensors

The active configuration is:

```text
UeSim/Content/model/config/config.json
```

The v1.0.13 release default contains IMU, odometry, GPS, RGB, depth, and Airy LiDAR entries. Confirm that the selected UI preset still provides the LiDAR, IMU, and odometry needed by navigation. Preset references include:

```text
UeSim/Content/model/config/sensors/config_default.json
UeSim/Content/model/config/sensors/mid360_slam.json
```

Relevant sensor fields:

```json
{
  "sensor_type": "mid360",
  "topic": "/front_lidar",
  "frequency": 10,
  "position": {"x": 0.0, "y": 0.0, "z": 0.1},
  "rotation": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
  "sensor_attach": "base_link",
  "simulate_motion_distortion": false
}
```

Use `sensor_sync_mode=true` for a common simulation-time schedule. Keep `simulate_motion_distortion=false` during basic integration unless the downstream localization stack explicitly deskews each point using correct per-point timing.

MATRiX sensor frames use ROS FLU: X forward, Y left, Z up, in metres.

## 5. Start MATRiX and verify Zenoh first

Terminal 1, from the MATRiX root:

```bash
./UeSim.sh
```

Terminal 2:

```bash
python3 Tools/zenoh_topic_monitor.py --key 'rt/**'
```

Do not continue to RoamerX until the monitor shows stable LiDAR, IMU, and odometry rates. The exact keys depend on the loaded sensor configuration. Common project defaults include:

```text
rt/front_lidar
rt/front_lidar/imu
rt/imu
rt/odom/mujoco_odom
```

Use observed keys rather than assuming every preset publishes all four.

Inspect LiDAR independently when needed:

```bash
python3 Tools/zenoh_sensor_receiver.py \
  --key 'rt/front_lidar' \
  --show-lidar
```

## 6. Start the Zenoh-to-ROS2 bridge

Use the bridge version paired with the current MATRiX message definitions. A common invocation is:

```bash
source /opt/ros/humble/setup.bash
source /path/to/bridge_ws/install/setup.bash

ros2 run ue_zenoh_bridge ue_zenoh_bridge \
  --endpoint tcp/127.0.0.1:7447 \
  --key-expr 'rt/**'
```

If the bridge runs on another machine, replace `127.0.0.1` with the MATRiX host and allow 7447/TCP.

Verify the bridge output before starting navigation:

```bash
ros2 topic list
ros2 topic hz /front_lidar
ros2 topic echo /imu --once
ros2 topic echo /odom/mujoco_odom --once
```

Topic names shown above are examples. Use `ros2 topic list` to identify the names produced by the installed bridge.

## 7. ROS environment consistency

All ROS 2 terminals participating in the same graph must use compatible settings. For example:

```bash
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ROS_DOMAIN_ID=89
source /path/to/genisom_roamerx_open/install/setup.bash
```

The values must match across bridge, RoamerX, RViz, TF publishers, and helper processes. `ROS_DOMAIN_ID=89` is an integration example, not a value exported by `UeSim.sh`.

## 8. TF contract

Before navigation, verify a connected transform tree containing the frames expected by the selected RoamerX configuration. A typical chain is:

```text
map -> odom -> base_link -> lidar_frame
                         -> imu_frame
```

Responsibilities should be unambiguous:

| Transform | Typical owner |
|---|---|
| `map -> odom` | localization or SLAM |
| `odom -> base_link` | odometry/bridge or one dedicated TF publisher |
| `base_link -> sensor` | static robot description or static TF publisher |

Never publish the same transform from two nodes. Check:

```bash
ros2 run tf2_tools view_frames
ros2 run tf2_ros tf2_echo odom base_link
ros2 run tf2_ros tf2_echo base_link front_lidar
```

If the installed RoamerX workspace does not contain an optional `pub_tf` package, use the bridge/robot description or a dedicated static TF publisher. Do not copy an unavailable launch command from old documentation.

## 9. Start RoamerX

Use the commands documented by the installed `genisom_roamerx_open` revision. If that revision still provides the helper script referenced by older releases, the sequence is typically:

```bash
cd /path/to/genisom_roamerx_open
bash script/bash/start_navigation.sh nav
```

In another terminal with the same ROS environment:

```bash
cd /path/to/genisom_roamerx_open
bash script/bash/start_navigation.sh rviz
```

First confirm the script and modes exist:

```bash
bash script/bash/start_navigation.sh --help
```

If the command differs, follow the checked-out RoamerX README. MATRiX does not install or update that external workspace.

## 10. Validation gates

Proceed in this order:

1. MATRiX advances simulation and publishes `rt/**` at stable rates.
2. LiDAR geometry and orientation are correct in the standalone receiver.
3. The bridge produces valid ROS 2 message types and timestamps.
4. `odom -> base_link` changes smoothly as the robot moves.
5. Static sensor transforms match `config.json` mounting poses.
6. RoamerX costmaps receive LiDAR and clear/update obstacles.
7. Localization remains stable during translation and rotation.
8. Only then send navigation goals.

Useful checks:

```bash
ros2 topic hz /front_lidar
ros2 topic hz /imu
ros2 topic hz /odom/mujoco_odom
ros2 topic echo /clock --once
ros2 node list
ros2 param get /controller_server use_sim_time
```

Adjust names to match the installed bridge and RoamerX configuration.

## 11. Common failures

### RoamerX sees no topics

- confirm the bridge, RoamerX, and RViz share `ROS_DOMAIN_ID` and RMW settings;
- source all required workspaces in each terminal;
- verify UeSim data at Zenoh level before debugging ROS 2;
- compare actual topic names and message types.

### Costmap is rotated or mirrored

MATRiX already publishes ROS FLU coordinates. A bridge must not invert Y or swap axes a second time. Verify the LiDAR frame and `base_link -> lidar_frame` transform.

### Obstacles smear while rotating

- keep `simulate_motion_distortion=false` for the baseline test;
- verify one cloud carries one coherent Header timestamp;
- check odometry time, TF availability, and downstream deskew settings;
- make sure the viewer/costmap replaces the latest cloud instead of accumulating scans indefinitely.

### TF extrapolation errors

Check clock source, message Header timestamps, TF publisher timestamps, buffer duration, and `use_sim_time`. Do not mix wall-clock and simulation-clock data paths.

### Robot does not move

The release defaults to built-in control with `robot.inside_mc=true`. If an external controller is required, download it separately, set `inside_mc=false`, configure its robot type, and start UeSim before the controller. See [Motion_Control.md](Motion_Control.md).

## 12. Removed stale assumptions

This maintained document intentionally does not prescribe:

- nonexistent MATRiX `bin/sim_launcher` or `open_sim_launcher` commands;
- a hard-coded `/workspace` container layout;
- editing `matrix/src/robot_mc/...` inside this binary package;
- running bridge processes as `root` without a demonstrated requirement;
- an optional `pub_tf` package that may not exist;
- RoamerX architecture, build, and hardware commands unrelated to MATRiX integration.

Those details must be maintained by the external RoamerX repository and the deployment environment.
