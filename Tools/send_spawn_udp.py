#!/usr/bin/env python3
"""Send a UE Sim spawn command over UDP.

Default payload matches the simple Blueprint test format:

{
  "protocol": "uesim.spawn",
  "version": 1,
  "action": "spawn",
  "objects": "car",
  "position": 10
}

Use --format protocol to send the documented object-array format.
"""

from __future__ import annotations

import argparse
import json
import socket
import time
import uuid
from typing import Any


SPAWN_TYPES = (
    "wall",
    "wire_fence",
    "chair",
    "car",
    "house",
    "generic_obstacle",
    "pedestrian",
)


def build_simple_payload(object_type: str, position_m: float) -> dict[str, Any]:
    return {
        "protocol": "uesim.spawn",
        "version": 1,
        "action": "spawn",
        "objects": object_type,
        "position": position_m,
    }


def build_protocol_payload(
    object_type: str,
    forward_m: float,
    right_m: float,
    up_m: float,
    yaw_deg: float,
) -> dict[str, Any]:
    object_id = f"{object_type}-{uuid.uuid4().hex[:8]}"
    return {
        "protocol": "uesim.spawn",
        "version": 1,
        "message_id": f"msg-{uuid.uuid4().hex[:8]}",
        "action": "spawn",
        "reference": {
            "type": "player",
            "id": "player",
        },
        "objects": [
            {
                "id": object_id,
                "type": object_type,
                "relative_position": {
                    "forward_m": forward_m,
                    "right_m": right_m,
                    "up_m": up_m,
                },
                "relative_rotation": {
                    "yaw_deg": yaw_deg,
                    "pitch_deg": 0,
                    "roll_deg": 0,
                },
                "scale": {
                    "x": 1,
                    "y": 1,
                    "z": 1,
                },
                "properties": {
                    "collision": True,
                },
            }
        ],
    }


def send_udp(host: str, port: int, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(data, (host, port))
    print(f"Sent UDP JSON to {host}:{port}")
    print(data.decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send UE Sim spawn JSON over UDP.")
    parser.add_argument("--host", default="127.0.0.1", help="UDP target host.")
    parser.add_argument("--port", type=int, default=8081, help="UDP target port.")
    parser.add_argument(
        "--type",
        choices=SPAWN_TYPES,
        default="car",
        help="Object type to spawn.",
    )
    parser.add_argument(
        "--position",
        type=float,
        default=10,
        help="Simple format position in meters, usually forward distance.",
    )
    parser.add_argument(
        "--forward",
        type=float,
        default=None,
        help="Protocol format forward distance in meters. Defaults to --position.",
    )
    parser.add_argument("--right", type=float, default=0, help="Right offset in meters.")
    parser.add_argument("--up", type=float, default=0, help="Up offset in meters.")
    parser.add_argument("--yaw", type=float, default=0, help="Relative yaw in degrees.")
    parser.add_argument(
        "--format",
        choices=("simple", "protocol"),
        default="simple",
        help="Payload format to send.",
    )
    parser.add_argument("--repeat", type=int, default=1, help="Number of messages to send.")
    parser.add_argument(
        "--interval",
        type=float,
        default=0.2,
        help="Delay in seconds between repeated messages.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    for index in range(args.repeat):
        if args.format == "simple":
            payload = build_simple_payload(args.type, args.position)
        else:
            forward_m = args.position if args.forward is None else args.forward
            payload = build_protocol_payload(
                object_type=args.type,
                forward_m=forward_m,
                right_m=args.right,
                up_m=args.up,
                yaw_deg=args.yaw,
            )

        send_udp(args.host, args.port, payload)

        if index < args.repeat - 1:
            time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
