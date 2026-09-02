# MATRiX v1.0.13 Getting Started

[Back to README](../README.md) | [中文](Getting_Started_CN.md)

## Download and extract

Download all three archive parts and `SHA256SUMS` from the [v1.0.13 Release](https://github.com/zsibot/matrix/releases/tag/v1.0.13), then run:

```bash
sha256sum -c SHA256SUMS
cat MATRiX_v1.0.13.tar.gz.part-* | tar -xzf -
```

See [Release_Download.md](Release_Download.md) for part sizes and complete checksums.

## Run

MATRiX runs on Linux x86_64 with a correctly installed graphics driver and is not limited to Ubuntu 22.04. At least 16 GB of memory is recommended. ROS 2 is optional.

```bash
cd MATRiX_v1.0.13
./UeSim.sh
```

No `chmod` step is required for `UeSim.sh` or `UeSim/Binaries/Linux/UeSim`.

Arguments pass through to UeSim:

```bash
./UeSim.sh -ResX=1280 -ResY=720 -Windowed
```

The runtime log is generated at `UeSim/Saved/Logs/UeSim.log`.

## Configuration

The active configuration is `UeSim/Content/model/config/config.json`. Release defaults include:

```text
mujoco_model: model/xgb/xgb.xml
inside_mc: true
network_mode: standalone
sensor_sync_mode: false
zenoh_router: tcp/0.0.0.0:7447
```

The relative model path remains valid when the release directory is moved.

## Motion control

Built-in control is enabled by default and requires no separate download:

```bash
./UeSim.sh
```

The release does not include an external `robot_mc`. See [Motion_Control.md](Motion_Control.md#optional-external-robot_mc-separate-download) to download it separately and manually edit `inside_mc`. Never run embedded and external controllers together.

## Zenoh and sensors

UeSim listens on `tcp/0.0.0.0:7447`; local tools connect to `tcp/127.0.0.1:7447`.

```bash
python3 -m pip install eclipse-zenoh numpy opencv-python matplotlib
python3 Tools/zenoh_topic_monitor.py --key '**'
python3 Tools/zenoh_topic_monitor.py --key 'rt/**'
python3 Tools/zenoh_sensor_receiver.py --key 'rt/**'
```

The default configuration contains IMU, odometry, GPS, RGB, depth, and Airy LiDAR. UI selections and presets can change active keys; use the topic monitor as the live source of truth. Presets are under `UeSim/Content/model/config/sensors/`.

## LiDAR-to-camera image projection

Install the tool dependencies, validate the selected sensors and calibration, then open the live overlay:

```bash
python3 -m pip install numpy opencv-python eclipse-zenoh
python3 Tools/visualize_lidar_camera_projection.py --check-only
python3 Tools/visualize_lidar_camera_projection.py
```

The tool reads `UeSim/Content/model/config/config.json` and connects to `tcp/127.0.0.1:7447` by default. Set `sensor_sync_mode=true` before use, and use matching camera/LiDAR frequencies and mounting frames. See [Lidar_Camera_Projection.md](Lidar_Camera_Projection.md).

## Map DLCs

No external map DLC is included, and `UeSim/Content/model/MapDataTable.json` intentionally starts with an empty `rows` array. Seeing no map cards initially is expected. Select **UPDATE LIST** to retrieve the latest catalog, then select **DOWNLOAD** below a map to download its DLC automatically. If needed, use the [manual Baidu Netdisk download (code: 6sth)](https://pan.baidu.com/s/1I87hQ9C8XzIGXgbyWk3i9A?pwd=6sth#list/path=%2F), place the extracted v1.0.13-compatible `.pak` in `UeSim/Saved/DLCs/`, and restart UeSim. See [Map_DLC.md](Map_DLC.md) for details.

## ROS 2 and Pixel Streaming

Zenoh is the primary transport. Use a bridge matching current message formats for ROS 2; see [RoamerX_Lite_Integration.md](RoamerX_Lite_Integration.md).

Pixel Streaming setup starts at `UeSim/Samples/PixelStreaming2/WebServers/get_ps_servers.sh`; see [pixelstreaming_tutorial.md](pixelstreaming_tutorial.md).

## Troubleshooting

- Model not found: restore a valid relative path such as `model/xgb/xgb.xml`.
- Vulkan or startup failure: inspect `UeSim/Saved/Logs/UeSim.log`.
- No Zenoh samples: subscribe to `**`, then verify IP, port 7447, firewall, logs, and sensor activation.
