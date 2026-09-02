# Controller and Camera Guide

[README](../README.md) | [中文](Controller_Guide_CN.md)

The current source separates robot motion input from simulation camera input. A packaged Blueprint or game mode can add or override bindings, so use the in-game help when it differs from this table.

## Embedded motion controller

| Action | Default gamepad input | Availability |
|---|---|---|
| Planar motion | Left stick | Embedded motion models |
| Yaw | Right stick horizontal axis | Embedded motion models |
| Enter Stand | LB + Y | All seven documented embedded motion models |
| Enter Passive | LB + RB | All seven documented embedded motion models |
| Jump | RB + X | `xgb` only |
| Front jump | RB + Y | `xgb` only |

Input modes are `Hardware`, `UDP`, `Auto`, and `Disabled`. Hardware input uses Unreal's cross-platform logical Gamepad keys; the source does not require a particular controller brand or a Linux `/dev/input/js0` path.

UDP input listens on `0.0.0.0:7447` by default and receives JSON gamepad state. This is UDP and is independent of the Zenoh TCP endpoint, even when both use port number 7447.

## Simulation camera and UI

The default project input configuration includes:

| Action | Default input |
|---|---|
| Move forward / backward | W / S |
| Turn left / right | A / D |
| Move vertically in supported camera modes | Q / E |
| Change camera | V |
| Toggle HUD | H |
| Pause / return | Esc |
| Look | Mouse axes |

Q/E behavior depends on the active free-flight or camera mode. W/A/S/D control the simulation camera/pawn; they are not a replacement for the embedded robot policy controls.
