#!/usr/bin/env python3
"""通过 Matrix_MC UDP JSON 手柄接口测试机器狗动作。

仅使用 Python 标准库。默认发送到本机 127.0.0.1:7447。
速度参数范围为 [-1.0, 1.0]：forward 正数前进，lateral 正数左移，
yaw 正数左转。
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from typing import Dict, Optional, Union


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7447
DEFAULT_RATE_HZ = 20.0

CommandValue = Union[float, int]
Command = Dict[str, CommandValue]


def clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def neutral_command() -> Command:
    return {
        "LX": 0.0,
        "LY": 0.0,
        "RX": 0.0,
        "RY": 0.0,
        "LT": 0.0,
        "RT": 0.0,
        "A": 0,
        "B": 0,
        "X": 0,
        "Y": 0,
        "LB": 0,
        "RB": 0,
        "VIEW": 0,
        "MENU": 0,
        "GUIDE": 0,
        "LS": 0,
        "RS": 0,
    }


class UdpRobotController:
    def __init__(self, host: str, port: int, rate_hz: float, verbose: bool) -> None:
        self.target = (host, port)
        self.period = 1.0 / rate_hz
        self.verbose = verbose
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self) -> None:
        self.socket.close()

    def send(self, command: Command) -> None:
        payload = json.dumps(command, separators=(",", ":")).encode("utf-8")
        self.socket.sendto(payload, self.target)
        if self.verbose:
            print(payload.decode("utf-8"))

    def hold(self, command: Command, duration: float) -> None:
        """持续发送，避免 Matrix_MC 的 UDP 输入在动作中超时。"""
        deadline = time.monotonic() + duration
        next_send = time.monotonic()
        while time.monotonic() < deadline:
            self.send(command)
            next_send += self.period
            delay = min(next_send, deadline) - time.monotonic()
            if delay > 0.0:
                time.sleep(delay)

    def neutral(self, duration: float = 0.15) -> None:
        self.hold(neutral_command(), duration)

    def pulse(self, **buttons: int) -> None:
        # C++ 端按组合键上升沿触发，所以必须先释放、按下、再释放。
        self.neutral(0.10)
        command = neutral_command()
        command.update(buttons)
        self.hold(command, 0.15)
        self.neutral(0.10)

    def stand(self, wait_seconds: float) -> None:
        print("触发起身：LB+Y")
        self.pulse(LB=1, Y=1)
        self.neutral(wait_seconds)
        print("请确认 Matrix_MC 日志已经显示 mode=STAND_HOLD。")

    def balance(self) -> None:
        print("停止移动并进入平衡站立：LB+B")
        self.pulse(LB=1, B=1)

    def joint_hold(self) -> None:
        print("保持当前关节位置：LB+X")
        self.pulse(LB=1, X=1)

    def passive(self) -> None:
        print("进入被动模式并停止输出力矩：LB+RB")
        self.pulse(LB=1, RB=1)

    def move(
        self,
        *,
        forward: float = 0.0,
        lateral: float = 0.0,
        yaw: float = 0.0,
        duration: float,
    ) -> None:
        command = neutral_command()
        # Matrix_MC 内部映射：forward=LY, lateral=-LX, yaw=-RX。
        command["LY"] = clamp(forward)
        command["LX"] = clamp(-lateral)
        command["RX"] = clamp(-yaw)
        try:
            self.hold(command, duration)
        finally:
            # 正常结束或 Ctrl+C 都归零并请求平衡站立。
            self.neutral(0.15)
            self.balance()

    def stunt(self, name: str, wait_seconds: float) -> None:
        buttons = {
            "jump": {"RB": 1, "X": 1},
            "front-jump": {"RB": 1, "Y": 1},
            "backflip": {"RB": 1, "B": 1},
            "sideflip": {"RB": 1, "VIEW": 1},
        }
        labels = {
            "jump": "跳跃 RB+X",
            "front-jump": "前跳 RB+Y",
            "backflip": "后空翻 RB+B",
            "sideflip": "侧翻 RB+Back",
        }
        print(f"触发动作：{labels[name]}")
        self.pulse(**buttons[name])
        self.neutral(wait_seconds)


def bounded_float(text: str) -> float:
    value = float(text)
    if not -1.0 <= value <= 1.0:
        raise argparse.ArgumentTypeError("速度必须在 -1.0 到 1.0 之间")
    return value


def positive_float(text: str) -> float:
    value = float(text)
    if value <= 0.0:
        raise argparse.ArgumentTypeError("必须大于 0")
    return value


def nonnegative_float(text: str) -> float:
    value = float(text)
    if value < 0.0:
        raise argparse.ArgumentTypeError("不能小于 0")
    return value


def add_stand_first(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stand-first", action="store_true", help="运动前先起身")
    parser.add_argument(
        "--stand-wait",
        type=nonnegative_float,
        default=3.0,
        metavar="SECONDS",
        help="起身等待时间（默认：3 秒）",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="通过 UDP 测试 Matrix_MC 的起身、站立、行走、转向和动作接口。"
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Matrix_MC 主机地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="UDP 端口")
    parser.add_argument(
        "--rate",
        type=positive_float,
        default=DEFAULT_RATE_HZ,
        metavar="HZ",
        help="发送频率（默认：20 Hz）",
    )
    parser.add_argument("--verbose", action="store_true", help="打印每个 JSON 报文")

    actions = parser.add_subparsers(dest="action", required=True)

    stand = actions.add_parser("stand", help="起身并等待站稳")
    stand.add_argument("--wait", type=nonnegative_float, default=3.0)
    actions.add_parser("balance", help="停止移动并进入平衡站立")
    actions.add_parser("hold", help="保持当前关节位置")
    actions.add_parser("passive", help="停止输出力矩，机器狗可能倒下")
    actions.add_parser("neutral", help="只发送摇杆和按键归零报文")

    walk = actions.add_parser("walk", help="前后、横移以及组合转向")
    walk.add_argument("--forward", type=bounded_float, default=0.30)
    walk.add_argument("--lateral", type=bounded_float, default=0.0)
    walk.add_argument("--yaw", type=bounded_float, default=0.0)
    walk.add_argument("--duration", type=positive_float, default=3.0)
    add_stand_first(walk)

    rotate = actions.add_parser("rotate", help="原地旋转")
    rotate.add_argument("--yaw", type=bounded_float, default=0.30)
    rotate.add_argument("--duration", type=positive_float, default=2.0)
    add_stand_first(rotate)

    stunt = actions.add_parser("stunt", help="触发跳跃或翻转测试")
    stunt.add_argument("name", choices=("jump", "front-jump", "backflip", "sideflip"))
    stunt.add_argument("--wait", type=nonnegative_float, default=4.0)
    stunt.add_argument(
        "--confirm-stunt",
        action="store_true",
        help="确认场景安全并允许触发跳跃/翻转",
    )

    demo = actions.add_parser("demo", help="起身、前进、横移、旋转测试序列")
    demo.add_argument("--stand-wait", type=nonnegative_float, default=3.0)
    demo.add_argument("--speed", type=bounded_float, default=0.25)
    demo.add_argument("--yaw", type=bounded_float, default=0.25)
    demo.add_argument("--duration", type=positive_float, default=2.0)
    demo.add_argument("--pause", type=nonnegative_float, default=0.75)

    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not 1 <= args.port <= 65535:
        parser.error("--port 必须在 1 到 65535 之间")
    if args.action == "walk":
        active = (
            abs(args.forward) > 0.12
            or abs(args.lateral) > 0.12
            or abs(args.yaw) > 0.18
        )
        if not active:
            parser.error("所有速度都位于 Matrix_MC 摇杆死区内")
    if args.action == "rotate" and abs(args.yaw) <= 0.18:
        parser.error("旋转速度必须越过 0.18 摇杆死区")
    if args.action == "stunt" and not args.confirm_stunt:
        parser.error("动作测试必须显式增加 --confirm-stunt")
    if args.action == "demo":
        if abs(args.speed) <= 0.12:
            parser.error("演示速度必须越过 0.12 摇杆死区")
        if abs(args.yaw) <= 0.18:
            parser.error("演示转向必须越过 0.18 摇杆死区")


def pause(controller: UdpRobotController, seconds: float) -> None:
    if seconds > 0.0:
        controller.neutral(seconds)


def run(args: argparse.Namespace, controller: UdpRobotController) -> None:
    if args.action == "stand":
        controller.stand(args.wait)
    elif args.action == "balance":
        controller.balance()
    elif args.action == "hold":
        controller.joint_hold()
    elif args.action == "passive":
        controller.passive()
    elif args.action == "neutral":
        controller.neutral(0.5)
    elif args.action in ("walk", "rotate"):
        if args.stand_first:
            controller.stand(args.stand_wait)
        if args.action == "walk":
            print(
                f"移动 {args.duration:.1f}s：前后={args.forward:.2f} "
                f"横移={args.lateral:.2f} 转向={args.yaw:.2f}"
            )
            controller.move(
                forward=args.forward,
                lateral=args.lateral,
                yaw=args.yaw,
                duration=args.duration,
            )
        else:
            print(f"原地旋转 {args.duration:.1f}s：转向={args.yaw:.2f}")
            controller.move(yaw=args.yaw, duration=args.duration)
    elif args.action == "stunt":
        controller.stunt(args.name, args.wait)
    elif args.action == "demo":
        controller.stand(args.stand_wait)
        print("演示：向前")
        controller.move(forward=args.speed, duration=args.duration)
        pause(controller, args.pause)
        print("演示：向左横移")
        controller.move(lateral=args.speed, duration=args.duration)
        pause(controller, args.pause)
        print("演示：向左旋转")
        controller.move(yaw=args.yaw, duration=args.duration)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    validate_args(parser, args)

    controller: Optional[UdpRobotController] = None
    try:
        controller = UdpRobotController(args.host, args.port, args.rate, args.verbose)
        print(f"UDP 目标：{args.host}:{args.port}，发送频率：{args.rate:g} Hz")
        run(args, controller)
        return 0
    except KeyboardInterrupt:
        print("\n已中断；正在发送摇杆归零报文。", file=sys.stderr)
        return 130
    except (OSError, ValueError) as error:
        print(f"UDP 控制失败：{error}", file=sys.stderr)
        return 1
    finally:
        if controller is not None:
            try:
                controller.neutral(0.15)
            except OSError:
                pass
            controller.close()


if __name__ == "__main__":
    raise SystemExit(main())
