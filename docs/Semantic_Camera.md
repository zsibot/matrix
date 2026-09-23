# Semantic camera — v1.1.2 rebuild

This guide targets the Linux runtime rebuilt on 2026-09-23 at 10:24 China Standard Time. Semantic capture is optional; the initial sensor dictionary is empty. Load and apply a scheme before capturing.

## Enable and receive

Load and apply `UeSim/Content/model/config/sensors/config_rgb_semantic.json` in sensor settings, then enter the simulation. The paired preset uses matching 640×480 images, 10 Hz, 90° FOV, mounting pose and intrinsics. Use `config_semantic.json` for semantic-only capture.

```bash
python3 Tools/zenoh_sensor_receiver.py --key 'rt/front_camera/**'
# For a custom topic without semantic/segmentation in its name:
python3 Tools/zenoh_sensor_receiver.py --key 'rt/custom_labels/**' --stream-type semantic
```

The sensor type is `semantic`; this is perspective ground-truth labeling from Actor Tags, not visual recognition. Output is ROS 2 CompressedImage over Zenoh, always lossless 8-bit PNG: R=G=B=class ID, A=255. Do not apply lossy compression, color transforms or bilinear resizing to the labels. The receiver adds a display palette and hover inspection without changing the source labels.

| Actor Tag / visible surface | Class ID |
|---|---:|
| Background / no visible surface | 0 |
| drive_plane | 10 |
| drive_stair | 20 |
| drive_other | 30 |
| human | 40 |
| vehicle | 50 |
| Visible unclassified surface | 255 |

Tags are Actor Tags, not Component Tags. Multiple recognized tags follow the order above. Unclassified occluders remain 255 and do not reveal classes behind them.

## RGB alignment and boundaries

Keep mounting frame, position, rotation, image dimensions, FOV, fx/fy/cx/cy, K1/K2/K3/P1/P2, mounting-actor visibility and rate identical. Keep `robot.sensor_sync_mode=true`. Semantic capture uses the same perspective distortion geometry as RGB, but nearest-neighbor class sampling avoids mixed IDs at boundaries.

The desktop deferred rendering path requires CustomDepth/Stencil (`r.CustomDepth=3`, configured in this project). Other effects writing stencil values need coordination. Transparent or custom renderers and Gaussian splats are not covered by the ordinary opaque-mesh path. Camera labels follow rendered surfaces; LiDAR follows collision geometry, so their outlines may differ. RGB anti-aliasing and motion blur can also mix edge colors. Panoramic and fisheye semantic output is not provided.

Binary/preset inclusion and offline decoding checks do not replace testing actual rendering on the target GPU and map.
