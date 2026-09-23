# MATRiX v1.1.2 release notes

Based on the Linux x86_64 package built on 2026-09-23 at 10:24 China Standard Time. Build ID: `20260923T022450476117Z-6596e3e1`. The binary and PAK files match the packaging history.

## Release defaults and behavior

- Default model: `xgb`, using `Content/model/xgb/xgb.xml` relative to `UeSim/`.
- Built-in motion control is enabled (`inside_mc=true`); `network_mode=standalone` and `sensor_sync_mode=true` are retained.
- The initial `robot.sensors` dictionary is empty. Load and apply a sensor scheme before entering the simulation and spawning the robot. Presets are not activated automatically.
- XXG is hidden in open-source mode and is not a selectable robot in this release.
- The six-sensor `config_default.json`, semantic-only `config_semantic.json`, and paired `config_rgb_semantic.json` presets remain available. Semantic images are lossless class-ID PNGs.
- Updated runtime and robot-selection UI assets; repaired the generated launcher and replaced the developer-specific absolute model path.
- Synchronized bilingual documentation, public configuration examples, tool instructions and the reusable split-archive build script.

## Upgrade

Extract v1.1.2 into a new directory and keep its runtime, Engine, plugins and models together. Back up old configuration and migrate selected fields instead of overwriting the new configuration directory. Start with `./UeSim.sh`.

Use **UPDATE LIST** and **DOWNLOAD** in map selection to install a compatible DLC. Built-in control needs no separate process. An external `robot_mc` must be downloaded separately and used with built-in control disabled.

Apply `config_default.json` for sensor checks or `config_rgb_semantic.json` for paired images. A tool's `--sensor-config` only selects its input file; it does not activate sensors in UeSim.

## Download and verification

Every GitHub archive part is below 2 GB. Download all parts and `SHA256SUMS`, verify, then concatenate and extract. Never mix versions. Select the latest Baidu Netdisk version. Direct and Baidu mirrors synchronize independently; use their actual version and supplied checksums.

## Validation scope

Pre-publication checks cover the launcher, Python tools, configuration, documentation links, compressed archive and part integrity. This publication workflow does not run a live GPU scene; source test records are not a substitute for interactive acceptance of this package.

The open-source runtime excludes `UeSim/Content/model/xxg`.
