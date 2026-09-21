#!/usr/bin/env python3
"""Reference client for the uesim.gimbal UDP JSON protocol v1.1."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import uuid
from typing import Any


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="127.0.0.1", help="gimbal server IPv4 address")
    parser.add_argument("--port", type=int, default=8870, help="gimbal control UDP port (default: 8870)")
    parser.add_argument("--local-address", default="0.0.0.0", help="local IPv4 address used with --local-port")
    parser.add_argument("--local-port", type=int, default=0, help="fixed local UDP receive port; 0 selects an ephemeral port")
    parser.add_argument("--gimbal-id", default="camera_gimbal")
    parser.add_argument("--client-id", default="uesim-reference-client")
    parser.add_argument("--session-id", default=str(uuid.uuid4()))
    parser.add_argument("--sequence", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=1.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common(parser)
    sub = parser.add_subparsers(dest="operation", required=True)

    for name in ("ping", "capabilities", "release"):
        sub.add_parser(name)

    listen_state = sub.add_parser("listen-state", help="listen for actively published state messages")
    listen_state.add_argument("--count", type=int, default=0, help="number of states to receive; 0 listens until Ctrl+C")

    speed = sub.add_parser("speed")
    speed.add_argument("mode", choices=("fine", "coarse", "custom"))

    custom = sub.add_parser("custom")
    custom.add_argument("--yaw-speed", type=float, required=True)
    custom.add_argument("--pitch-speed", type=float, required=True)
    custom.add_argument("--yaw-accel", type=float, required=True)
    custom.add_argument("--pitch-accel", type=float, required=True)
    custom.add_argument("--brake", type=float, required=True)
    custom.add_argument("--step", type=float, required=True)

    velocity = sub.add_parser("velocity")
    velocity.add_argument("yaw_rate_dps", type=float)
    velocity.add_argument("pitch_rate_dps", type=float)

    direction = sub.add_parser("direction")
    direction.add_argument("yaw_input", type=float, help="normalized input in [-1, 1]")
    direction.add_argument("pitch_input", type=float, help="normalized input in [-1, 1]")

    step = sub.add_parser("step")
    step.add_argument("yaw_delta_deg", type=float)
    step.add_argument("pitch_delta_deg", type=float)

    angle = sub.add_parser("angle")
    angle.add_argument("yaw_deg", type=float)
    angle.add_argument("pitch_deg", type=float)
    angle.add_argument("--travel", choices=("shortest", "clockwise", "counterclockwise"), default="shortest")
    angle.add_argument("--allow-clamp", action="store_true")

    stop = sub.add_parser("stop")
    stop.add_argument("axis", choices=("yaw", "pitch", "all"), default="all", nargs="?")

    stabilization = sub.add_parser("stabilization")
    stabilization.add_argument("mode", choices=("off", "follow_damping", "world_lock"))
    stabilization.add_argument("--gain", type=float)
    stabilization.add_argument("--response-hz", type=float)
    stabilization.add_argument("--max-offset-deg", type=float)
    stabilization.add_argument("--max-rate-dps", type=float)
    return parser


def command_and_params(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    operation = args.operation
    if operation in ("ping", "capabilities", "release"):
        return {
            "capabilities": "get_capabilities",
            "release": "release_control",
        }.get(operation, operation), {}
    if operation == "speed":
        return "set_speed_mode", {"mode": args.mode}
    if operation == "custom":
        return "set_custom_speed", {
            "yaw_speed_dps": args.yaw_speed,
            "pitch_speed_dps": args.pitch_speed,
            "yaw_acceleration_dps2": args.yaw_accel,
            "pitch_acceleration_dps2": args.pitch_accel,
            "brake_deceleration_dps2": args.brake,
            "step_deg": args.step,
        }
    if operation == "velocity":
        return "set_velocity", {
            "yaw_rate_dps": args.yaw_rate_dps,
            "pitch_rate_dps": args.pitch_rate_dps,
        }
    if operation == "direction":
        return "set_direction", {"yaw_input": args.yaw_input, "pitch_input": args.pitch_input}
    if operation == "step":
        return "step", {"yaw_delta_deg": args.yaw_delta_deg, "pitch_delta_deg": args.pitch_delta_deg}
    if operation == "angle":
        return "set_angle", {
            "yaw_deg": args.yaw_deg,
            "pitch_deg": args.pitch_deg,
            "yaw_travel": args.travel,
            "allow_clamp": args.allow_clamp,
        }
    if operation == "stop":
        return "stop_motion", {"axis": args.axis}
    if operation == "stabilization":
        params: dict[str, Any] = {"enabled": args.mode != "off", "mode": args.mode}
        optional = {
            "gain": args.gain,
            "response_hz": args.response_hz,
            "max_offset_deg": args.max_offset_deg,
            "max_rate_dps": args.max_rate_dps,
        }
        params.update({key: value for key, value in optional.items() if value is not None})
        return "set_stabilization", params
    raise AssertionError(f"unsupported operation: {operation}")


def main() -> int:
    args = build_parser().parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be in [1, 65535]")
    if not 0 <= args.local_port <= 65535:
        raise SystemExit("--local-port must be 0 or in [1, 65535]")
    if args.operation == "listen-state" and args.count < 0:
        raise SystemExit("--count must be >= 0")

    if args.operation == "listen-state":
        if not args.local_port:
            raise SystemExit("listen-state requires --local-port (normally 8871)")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.bind((args.local_address, args.local_port))
            received = 0
            try:
                while args.count == 0 or received < args.count:
                    response, source = udp.recvfrom(65507)
                    try:
                        decoded = json.loads(response.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        print(f"invalid state datagram from {source}: {error}", file=sys.stderr)
                        continue
                    if (decoded.get("protocol") != "uesim.gimbal" or
                            decoded.get("version") != "1.1" or decoded.get("type") != "state"):
                        print(f"ignored non-state datagram from {source}", file=sys.stderr)
                        continue
                    print(json.dumps(decoded, ensure_ascii=False, separators=(",", ":")), flush=True)
                    received += 1
            except KeyboardInterrupt:
                return 0
        return 0

    command, params = command_and_params(args)

    next_sequence = args.sequence if args.sequence is not None else int(time.time() * 1000)

    def make_payload() -> bytes:
        nonlocal next_sequence
        request = {
            "protocol": "uesim.gimbal",
            "version": "1.1",
            "type": "request",
            "request_id": str(uuid.uuid4()),
            "client_id": args.client_id,
            "session_id": args.session_id,
            "sequence": next_sequence,
            "client_time_ms": int(time.time() * 1000),
            "gimbal_id": args.gimbal_id,
            "command": command,
            "reply_required": True,
            "params": params,
        }
        next_sequence += 1
        encoded = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > 4096:
            raise SystemExit(f"request is {len(encoded)} bytes; protocol limit is 4096")
        return encoded

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        udp.settimeout(args.timeout)
        if args.local_port:
            udp.bind((args.local_address, args.local_port))

        udp.sendto(make_payload(), (args.host, args.port))
        try:
            response, source = udp.recvfrom(65507)
        except TimeoutError:
            print("timed out waiting for a response", file=sys.stderr)
            return 2
        except ConnectionResetError:
            print(f"UDP endpoint {args.host}:{args.port} is unreachable", file=sys.stderr)
            return 2
        try:
            decoded = json.loads(response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            print(f"invalid response from {source}: {error}", file=sys.stderr)
            return 3
        print(json.dumps(decoded, ensure_ascii=False, indent=2))
        return 0 if decoded.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
