# Controller and Camera Guide

[README](../README.md) | [中文](Controller_Guide_CN.md)

MATRiX v1.0.13 separates robot motion input from simulation camera input. A packaged Blueprint or game mode can add or override bindings, so use the in-game help when it differs from this table.

## Embedded motion controller

| Action | Default gamepad input | Availability |
|---|---|---|
| Planar motion | Left stick | Embedded motion models |
| Yaw | Right stick horizontal axis | Embedded motion models |
| Enter Stand | LB + Y | All eight documented embedded motion models |
| Enter Balance Stand | LB + B | All eight documented embedded motion models |
| Joint hold | LB + X | All eight documented embedded motion models |
| Enter Passive | LB + RB | All eight documented embedded motion models |
| Jump | RB + X | `xgb` only |
| Front jump | RB + Y | `xgb` only |

Input modes are `Hardware`, `UDP`, `Auto`, and `Disabled`. The v1.0.13 Linux runtime reads `/dev/input/js0` by default when hardware input is active. In `Auto` mode, a recent UDP packet takes priority; otherwise the controller reads the gamepad.

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
