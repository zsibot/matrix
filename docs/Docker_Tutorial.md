# Docker Support Status

[README](../README.md) | [中文快速开始](Getting_Started_CN.md)

The current MATRiX documentation repository and the reviewed `uesim` source tree do not contain an official Dockerfile, container image definition, `scripts/docker/docker_run_gpu.sh`, or `scripts/docker/entrypoint.sh`.

As a result, the previous Docker tutorial could not be verified against the simulator source and has been retired. Commands that referenced `zsibot/matrix:latest` or `./bin/sim_launcher` should not be treated as a supported current workflow.

## What the source does verify

- The Unreal project and relevant native plugins contain Win64 and Linux build targets.
- Linux rendering is configured for Vulkan/Shader Model 6.
- MuJoCo native libraries are packaged for supported desktop targets.
- Pixel Streaming 2 is enabled in the project, but its web server setup is separate from containerization.

These facts make a custom Linux container possible, but they do not define a reproducible image, runtime dependency set, entrypoint, X11/Wayland strategy, GPU runtime policy, or redistribution license.

## Recommended path

Use the native packaged Linux release when available. If your team needs containers, build and maintain a project-specific image from the exact packaged release and document at least:

1. the base distribution and GPU driver compatibility;
2. NVIDIA Container Toolkit or another GPU runtime;
3. Vulkan device and ICD access;
4. display transport or headless/Pixel Streaming mode;
5. Zenoh TCP/UDP and signalling ports;
6. input and shared-memory requirements;
7. the MATRiX release and DLC versions included in the image.

Do not publish an image containing Unreal Engine, third-party assets, or proprietary control models until their redistribution terms have been reviewed.

An official Docker guide can be restored when the repository contains a tested Dockerfile, entrypoint, launch script, and CI smoke test.
