#!/usr/bin/env python3
"""Send independent JSON messages and MP3 voice data to UeSim over UDP."""

from __future__ import annotations

import argparse
import json
import socket
import struct
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterator


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8868
DEFAULT_CHUNK_SIZE = 60_000
MAX_UDP_PAYLOAD = 65_507

VOICE_MAGIC = b"UESA"
VOICE_VERSION = 1
VOICE_FORMAT_MP3 = 1
VOICE_HEADER = struct.Struct("!4sBB16sHHI")


def send_json_message(
    message: Mapping[str, Any],
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> int:
    """Send one UTF-8 JSON UDP datagram and return its byte count."""
    packet = json.dumps(
        dict(message), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(packet) > MAX_UDP_PAYLOAD:
        raise ValueError(
            f"JSON packet is {len(packet)} bytes; UDP allows at most "
            f"{MAX_UDP_PAYLOAD} bytes"
        )

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        return udp_socket.sendto(packet, (host, port))


def build_voice_packets(
    mp3_data: bytes,
    *,
    message_id: uuid.UUID | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Iterator[bytes]:
    """Yield binary MP3 packets; voice bytes are not embedded in JSON."""
    if not mp3_data:
        raise ValueError("MP3 file is empty")
    if not (
        mp3_data.startswith(b"ID3")
        or (len(mp3_data) >= 2 and mp3_data[0] == 0xFF and mp3_data[1] & 0xE0 == 0xE0)
    ):
        raise ValueError("File does not have a valid MP3 header")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if VOICE_HEADER.size + chunk_size > MAX_UDP_PAYLOAD:
        raise ValueError(
            f"chunk_size must be at most {MAX_UDP_PAYLOAD - VOICE_HEADER.size}"
        )

    message_id = message_id or uuid.uuid4()
    chunk_count = (len(mp3_data) + chunk_size - 1) // chunk_size
    if chunk_count > 0xFFFF:
        raise ValueError("MP3 requires more than 65535 UDP chunks")

    for chunk_index in range(chunk_count):
        start = chunk_index * chunk_size
        chunk = mp3_data[start : start + chunk_size]
        header = VOICE_HEADER.pack(
            VOICE_MAGIC,
            VOICE_VERSION,
            VOICE_FORMAT_MP3,
            message_id.bytes,
            chunk_index,
            chunk_count,
            len(mp3_data),
        )
        yield header + chunk


def send_voice(
    mp3_path: str | Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    delay: float = 0.01,
) -> tuple[int, int]:
    """Send an MP3 as binary UDP chunks and return (file bytes, packet count)."""
    path = Path(mp3_path)
    if not path.is_file():
        raise FileNotFoundError(f"MP3 file not found: {path}")
    if path.suffix.lower() != ".mp3":
        raise ValueError(f"Expected an .mp3 file: {path}")
    if delay < 0:
        raise ValueError("delay cannot be negative")

    mp3_data = path.read_bytes()
    packets = list(build_voice_packets(mp3_data, chunk_size=chunk_size))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        for index, packet in enumerate(packets):
            udp_socket.sendto(packet, (host, port))
            if delay > 0 and index + 1 < len(packets):
                time.sleep(delay)
    return len(mp3_data), len(packets)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send independent JSON or MP3 messages to UeSim."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    json_parser = subparsers.add_parser("json", help="send one JSON message")
    json_parser.add_argument(
        "data",
        nargs="?",
        help='JSON object; in Windows PowerShell escape quotes as: {\\\"action\\\":1}',
    )
    json_parser.add_argument(
        "--action",
        type=int,
        help="send a numeric action without command-line JSON quoting",
    )
    json_parser.add_argument("--host", default=DEFAULT_HOST)
    json_parser.add_argument("--port", type=int, default=DEFAULT_PORT)

    voice_parser = subparsers.add_parser("voice", help="send one MP3")
    voice_parser.add_argument("mp3", type=Path)
    voice_parser.add_argument("--host", default=DEFAULT_HOST)
    voice_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    voice_parser.add_argument(
        "--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE
    )
    voice_parser.add_argument("--delay", type=float, default=0.01)
    voice_parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.port <= 65_535:
        raise SystemExit("--port must be between 1 and 65535")

    if args.command == "json":
        if args.action is not None:
            if args.data is not None:
                raise SystemExit("Use either JSON data or --action, not both")
            message = {"action": args.action}
        else:
            if args.data is None:
                raise SystemExit("Provide JSON data or use --action NUMBER")
            try:
                message = json.loads(args.data)
            except json.JSONDecodeError as error:
                raise SystemExit(
                    f"Invalid JSON received by Python: {args.data!r}\n"
                    "On Windows PowerShell use --action 1, or escape JSON "
                    r"quotes as: '{\"action\":1}'"
                ) from error
        if not isinstance(message, dict):
            raise SystemExit("JSON message must be an object")
        sent_bytes = send_json_message(message, args.host, args.port)
        print(f"sent {sent_bytes} JSON bytes to {args.host}:{args.port}")
        return 0

    mp3_data = args.mp3.read_bytes()
    packets = list(build_voice_packets(mp3_data, chunk_size=args.chunk_size))
    if args.dry_run:
        sizes = ", ".join(str(len(packet)) for packet in packets)
        print(
            f"valid: {len(mp3_data)} MP3 bytes, {len(packets)} binary UDP "
            f"packets ({sizes} bytes)"
        )
        return 0

    byte_count, packet_count = send_voice(
        args.mp3,
        args.host,
        args.port,
        chunk_size=args.chunk_size,
        delay=args.delay,
    )
    print(
        f"sent {byte_count} MP3 bytes in {packet_count} binary packets "
        f"to {args.host}:{args.port}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
