#!/usr/bin/env python3
"""Four-button coarse/fine control UI for the uesim.gimbal UDP protocol."""

from __future__ import annotations

import argparse
import json
import queue
import socket
import sys
import threading
import time
import uuid

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError as error:  # pragma: no cover
    raise SystemExit("This Python installation does not include tkinter/Tk.") from error


class GimbalUdpSender:
    """Thread-safe fire-and-forget sender with one stable protocol session."""

    def __init__(self, host: str, port: int, gimbal_id: str) -> None:
        try:
            self.endpoint = (socket.inet_ntoa(socket.inet_aton(host)), port)
        except OSError as error:
            raise ValueError("host must be a valid IPv4 address") from error
        if not 1024 <= port <= 65535:
            raise ValueError("port must be in [1024, 65535]")
        if not gimbal_id or len(gimbal_id) > 64:
            raise ValueError("gimbal-id must contain 1 to 64 characters")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-*")
        if any(character not in allowed for character in gimbal_id):
            raise ValueError("gimbal-id contains a character not allowed by protocol v1.1")

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        hostname = "".join(
            character if character.isascii() and (character.isalnum() or character in "._:-") else "-"
            for character in socket.gethostname()
        )
        self.client_id = f"gimbal-ui-{hostname}"[:64]
        self.session_id = str(uuid.uuid4())
        self.gimbal_id = gimbal_id
        self.sequence = 0
        self.lock = threading.Lock()
        self.closed = False

    def send(self, command: str, params: dict[str, object]) -> None:
        with self.lock:
            if self.closed:
                return
            self.sequence += 1
            request = {
                "protocol": "uesim.gimbal",
                "version": "1.1",
                "type": "request",
                "request_id": str(uuid.uuid4()),
                "client_id": self.client_id,
                "session_id": self.session_id,
                "sequence": self.sequence,
                "client_time_ms": int(time.time() * 1000),
                "gimbal_id": self.gimbal_id,
                "command": command,
                "reply_required": False,
                "params": params,
            }
            payload = json.dumps(
                request,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
            if len(payload) > 4096:
                raise ValueError("UDP JSON request exceeds 4096 bytes")
            self.socket.sendto(payload, self.endpoint)

    def close(self, send_stop: bool = True) -> None:
        with self.lock:
            if self.closed:
                return
        if send_stop:
            try:
                self.send("stop_motion", {"axis": "all"})
                self.send("release_control", {})
            except OSError:
                pass
        with self.lock:
            self.closed = True
            self.socket.close()


class GimbalStateReceiver:
    """Background receiver for protocol v1.1 actively published state messages."""

    def __init__(self, bind_address: str, port: int, gimbal_id: str) -> None:
        try:
            self.bind_address = socket.inet_ntoa(socket.inet_aton(bind_address))
        except OSError as error:
            raise ValueError("state-bind-address must be a valid IPv4 address") from error
        if not 1024 <= port <= 65535:
            raise ValueError("state-port must be in [1024, 65535]")

        self.port = port
        self.gimbal_id = gimbal_id
        self.updates: queue.Queue[tuple[dict[str, object], tuple[str, int], float]] = queue.Queue(maxsize=2)
        self.stop_event = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind((self.bind_address, self.port))
            self.socket.settimeout(0.2)
        except OSError:
            self.socket.close()
            raise
        self.worker = threading.Thread(target=self._receive_loop, name="GimbalStateReceiver", daemon=True)
        self.worker.start()

    def _receive_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                payload, source = self.socket.recvfrom(65507)
            except socket.timeout:
                continue
            except OSError:
                if not self.stop_event.is_set():
                    print("gimbal state receiver socket failed", file=sys.stderr)
                return

            try:
                message = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(message, dict):
                continue
            if (
                message.get("protocol") != "uesim.gimbal"
                or message.get("version") != "1.1"
                or message.get("type") != "state"
                or message.get("gimbal_id") != self.gimbal_id
                or not isinstance(message.get("data"), dict)
            ):
                continue

            update = (message, source, time.monotonic())
            if self.updates.full():
                try:
                    self.updates.get_nowait()
                except queue.Empty:
                    pass
            self.updates.put_nowait(update)

    def take_latest(self) -> tuple[dict[str, object], tuple[str, int], float] | None:
        latest = None
        while True:
            try:
                latest = self.updates.get_nowait()
            except queue.Empty:
                return latest

    def close(self) -> None:
        self.stop_event.set()
        self.socket.close()
        self.worker.join(timeout=0.5)


class NpcStateReceiver:
    """Receive the latest task-NPC UDP message without assuming a JSON schema."""

    def __init__(self, bind_address: str, port: int) -> None:
        try:
            self.bind_address = socket.inet_ntoa(socket.inet_aton(bind_address))
        except OSError as error:
            raise ValueError("npc state bind address must be a valid IPv4 address") from error
        if not 1024 <= port <= 65535:
            raise ValueError("npc-state-port must be in [1024, 65535]")

        self.port = port
        self.updates: queue.Queue[
            tuple[object, tuple[str, int], float, int, str | None]
        ] = queue.Queue(maxsize=2)
        self.stop_event = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind((self.bind_address, self.port))
            self.socket.settimeout(0.2)
        except OSError:
            self.socket.close()
            raise
        self.worker = threading.Thread(
            target=self._receive_loop,
            name="NpcStateReceiver",
            daemon=True,
        )
        self.worker.start()

    def _receive_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                payload, source = self.socket.recvfrom(65507)
            except socket.timeout:
                continue
            except OSError:
                if not self.stop_event.is_set():
                    print("NPC state receiver socket failed", file=sys.stderr)
                return

            error_text: str | None = None
            try:
                document: object = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                document = payload.decode("utf-8", errors="replace")
                error_text = f"Invalid UTF-8 JSON: {error}"

            update = (document, source, time.monotonic(), len(payload), error_text)
            if self.updates.full():
                try:
                    self.updates.get_nowait()
                except queue.Empty:
                    pass
            self.updates.put_nowait(update)

    def take_latest(
        self,
    ) -> tuple[object, tuple[str, int], float, int, str | None] | None:
        latest = None
        while True:
            try:
                latest = self.updates.get_nowait()
            except queue.Empty:
                return latest

    def close(self) -> None:
        self.stop_event.set()
        self.socket.close()
        self.worker.join(timeout=0.5)


class FourButtonGimbalUi:
    def __init__(
        self,
        root: tk.Tk,
        sender: GimbalUdpSender,
        state_receiver: GimbalStateReceiver,
        npc_state_receiver: NpcStateReceiver,
        frequency_hz: float,
        speed_scale: float,
        initial_speed_mode: str,
    ) -> None:
        self.root = root
        self.sender = sender
        self.state_receiver = state_receiver
        self.npc_state_receiver = npc_state_receiver
        self.period_seconds = 1.0 / frequency_hz
        self.speed_scale = speed_scale
        self.pressed: set[str] = set()
        self.control_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.last_state_received_at: float | None = None
        self.last_npc_state_received_at: float | None = None
        self.speed_mode = tk.StringVar(value=initial_speed_mode)
        self.speed_mode_text = tk.StringVar(value="模式状态：等待云台确认…")
        root.title("云台控制")
        root.geometry("620x760")
        root.minsize(460, 600)
        root.protocol("WM_DELETE_WINDOW", self.close)

        outer = ttk.Frame(root, padding=14)
        outer.pack(fill="both", expand=True)

        state_frame = ttk.LabelFrame(outer, text="云台状态", padding=10)
        state_frame.pack(fill="x", pady=(0, 12))
        self.connection_text = tk.StringVar(value=f"等待 UDP {state_receiver.port} 状态消息…")
        self.angle_text = tk.StringVar(value="Yaw: --    Pitch: --")
        self.rate_text = tk.StringVar(value="角速度: Yaw --    Pitch --")
        self.stabilization_text = tk.StringVar(value="防抖: --")
        ttk.Label(state_frame, textvariable=self.connection_text).pack(anchor="w")
        ttk.Label(state_frame, textvariable=self.angle_text).pack(anchor="w", pady=(5, 0))
        ttk.Label(state_frame, textvariable=self.rate_text).pack(anchor="w")
        ttk.Label(state_frame, textvariable=self.stabilization_text).pack(anchor="w")

        mode_frame = ttk.LabelFrame(outer, text="控制模式", padding=10)
        mode_frame.pack(fill="x", pady=(0, 12))
        mode_frame.columnconfigure(0, weight=1)
        mode_frame.columnconfigure(1, weight=1)
        ttk.Radiobutton(
            mode_frame,
            text="细调",
            value="fine",
            variable=self.speed_mode,
            command=lambda: self._set_speed_mode("fine"),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5), ipady=4)
        ttk.Radiobutton(
            mode_frame,
            text="粗调",
            value="coarse",
            variable=self.speed_mode,
            command=lambda: self._set_speed_mode("coarse"),
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0), ipady=4)
        ttk.Label(mode_frame, textvariable=self.speed_mode_text).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(7, 0),
        )

        frame = ttk.LabelFrame(outer, text="方向控制", padding=8)
        frame.pack(fill="x", pady=(0, 12))
        for index in range(3):
            frame.columnconfigure(index, weight=1)
            frame.rowconfigure(index, minsize=44)

        self._add_button(frame, "上", "up", 0, 1)
        self._add_button(frame, "左", "left", 1, 0)
        self._add_button(frame, "右", "right", 1, 2)
        self._add_button(frame, "下", "down", 2, 1)

        npc_frame = ttk.LabelFrame(
            outer,
            text=f"任务 NPC 状态（UDP {npc_state_receiver.port}）",
            padding=8,
        )
        npc_frame.pack(fill="both", expand=True)
        self.npc_connection_text = tk.StringVar(value="等待 NPC 状态消息…")
        ttk.Label(npc_frame, textvariable=self.npc_connection_text).pack(anchor="w")

        npc_body = ttk.Frame(npc_frame)
        npc_body.pack(fill="both", expand=True, pady=(5, 0))
        npc_body.columnconfigure(0, weight=1)
        npc_body.rowconfigure(0, weight=1)
        self.npc_text = tk.Text(
            npc_body,
            height=18,
            wrap="none",
            font=("Consolas", 10),
            state="disabled",
        )
        npc_vertical_scrollbar = ttk.Scrollbar(
            npc_body,
            orient="vertical",
            command=self.npc_text.yview,
        )
        npc_horizontal_scrollbar = ttk.Scrollbar(
            npc_body,
            orient="horizontal",
            command=self.npc_text.xview,
        )
        self.npc_text.configure(
            yscrollcommand=npc_vertical_scrollbar.set,
            xscrollcommand=npc_horizontal_scrollbar.set,
        )
        self.npc_text.grid(row=0, column=0, sticky="nsew")
        npc_vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        npc_horizontal_scrollbar.grid(row=1, column=0, sticky="ew")

        # Establish a deterministic initial mode before direction packets can be
        # emitted by the worker. The actively published state confirms it later.
        self._set_speed_mode(initial_speed_mode)
        self.worker = threading.Thread(target=self._control_loop, name="GimbalFourButtonControl", daemon=True)
        self.worker.start()
        self.root.after(50, self._poll_state)
        self.root.after(100, self._poll_npc_state)

    def _add_button(self, parent: ttk.Frame, text: str, direction: str, row: int, column: int) -> None:
        button = ttk.Button(parent, text=text)
        button.grid(row=row, column=column, sticky="nsew", padx=5, pady=3, ipadx=12, ipady=5)
        button.bind("<ButtonPress-1>", lambda _event, value=direction: self._press(value))
        button.bind("<ButtonRelease-1>", lambda _event, value=direction: self._release(value))

    def _press(self, direction: str) -> None:
        with self.control_lock:
            self.pressed.add(direction)

    def _release(self, direction: str) -> None:
        with self.control_lock:
            self.pressed.discard(direction)
            is_idle = not self.pressed
        if is_idle:
            self._send_stop()

    def _set_speed_mode(self, mode: str) -> None:
        if mode not in {"fine", "coarse"}:
            return
        try:
            # Serialize the discrete mode request with direction packets. This
            # guarantees the next set_direction datagram uses the new mode.
            with self.control_lock:
                self.sender.send("set_speed_mode", {"mode": mode})
            self.speed_mode.set(mode)
            label = "细调" if mode == "fine" else "粗调"
            self.speed_mode_text.set(f"已请求：{label}（等待状态确认）")
        except (OSError, ValueError) as error:
            self._show_error(str(error))

    def _control_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                # Keep this lock through sendto. Button release then waits for any
                # in-flight direction packet and sends stop afterward, preventing a
                # stale direction packet from reactivating motion after release.
                with self.control_lock:
                    yaw = (float("right" in self.pressed) - float("left" in self.pressed)) * self.speed_scale
                    pitch = (float("up" in self.pressed) - float("down" in self.pressed)) * self.speed_scale
                    if yaw != 0.0 or pitch != 0.0:
                        self.sender.send("set_direction", {"yaw_input": yaw, "pitch_input": pitch})
            except (OSError, ValueError) as error:
                print(f"UDP send failed: {error}", file=sys.stderr)
                self.stop_event.wait(0.2)
            self.stop_event.wait(self.period_seconds)

    def _send_stop(self) -> None:
        try:
            self.sender.send("stop_motion", {"axis": "all"})
        except (OSError, ValueError) as error:
            self._show_error(str(error))

    @staticmethod
    def _number(value: object) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f"{float(value):.2f}"
        return "--"

    def _poll_state(self) -> None:
        if self.stop_event.is_set():
            return
        latest = self.state_receiver.take_latest()
        if latest is not None:
            message, source, received_at = latest
            self.last_state_received_at = received_at
            data = message["data"]
            current = data.get("current", {})
            stabilization = data.get("stabilization", {})
            if not isinstance(current, dict):
                current = {}
            if not isinstance(stabilization, dict):
                stabilization = {}
            sequence = message.get("sequence", "--")
            self.connection_text.set(f"已连接  {source[0]}:{source[1]}  序号 {sequence}")
            speed_mode = data.get("speed_mode")
            if speed_mode in {"fine", "coarse"}:
                self.speed_mode.set(speed_mode)
                mode_label = "细调" if speed_mode == "fine" else "粗调"
                self.speed_mode_text.set(f"当前模式：{mode_label}")
            elif speed_mode == "custom":
                self.speed_mode.set("")
                self.speed_mode_text.set("当前模式：自定义（可切换为细调或粗调）")
            self.angle_text.set(
                f"Yaw: {self._number(current.get('yaw_deg'))}°    "
                f"Pitch: {self._number(current.get('pitch_deg'))}°"
            )
            self.rate_text.set(
                f"角速度: Yaw {self._number(current.get('yaw_rate_dps'))}°/s    "
                f"Pitch {self._number(current.get('pitch_rate_dps'))}°/s"
            )
            enabled = stabilization.get("enabled") is True
            mode = stabilization.get("mode", "--")
            self.stabilization_text.set(f"防抖: {'开启' if enabled else '关闭'}  模式: {mode}")
        elif self.last_state_received_at is not None:
            age = time.monotonic() - self.last_state_received_at
            if age >= 0.5:
                self.connection_text.set(f"状态超时  已 {age:.1f} 秒未收到 UDP {self.state_receiver.port}")
        self.root.after(50, self._poll_state)

    def _set_npc_text(self, value: str) -> None:
        max_characters = 16000
        if len(value) > max_characters:
            value = value[:max_characters] + "\n…（内容过长，已截断显示）"
        had_content = self.npc_text.index("end-1c") != "1.0"
        horizontal_position = self.npc_text.xview()[0]
        vertical_position = self.npc_text.yview()[0]
        self.npc_text.configure(state="normal")
        self.npc_text.delete("1.0", tk.END)
        self.npc_text.insert("1.0", value)
        self.npc_text.configure(state="disabled")
        if had_content:
            # The state may update at 10 Hz. Keep the user's scroll position so
            # lower JSON fields remain readable while new packets arrive.
            self.npc_text.xview_moveto(horizontal_position)
            self.npc_text.yview_moveto(vertical_position)

    def _poll_npc_state(self) -> None:
        if self.stop_event.is_set():
            return
        latest = self.npc_state_receiver.take_latest()
        if latest is not None:
            document, source, received_at, payload_size, error_text = latest
            self.last_npc_state_received_at = received_at
            source_text = f"{source[0]}:{source[1]}"
            if error_text is None:
                self.npc_connection_text.set(
                    f"已接收  来源 {source_text}  {payload_size} 字节"
                )
                self._set_npc_text(
                    json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
                )
            else:
                self.npc_connection_text.set(
                    f"格式异常  来源 {source_text}  {payload_size} 字节"
                )
                self._set_npc_text(f"{error_text}\n\n{document}")
        elif self.last_npc_state_received_at is not None:
            age = time.monotonic() - self.last_npc_state_received_at
            self.npc_connection_text.set(f"最后一条 NPC 状态：{age:.1f} 秒前")
        self.root.after(100, self._poll_npc_state)

    def _show_error(self, detail: str) -> None:
        if not self.stop_event.is_set():
            messagebox.showerror("UDP发送失败", detail, parent=self.root)

    def close(self) -> None:
        with self.control_lock:
            self.pressed.clear()
        self.stop_event.set()
        self.worker.join(timeout=0.3)
        self.state_receiver.close()
        self.npc_state_receiver.close()
        self.sender.close()
        self.root.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="gimbal server IPv4 address")
    parser.add_argument("--port", type=int, default=8870, help="gimbal UDP port (default: 8870)")
    parser.add_argument("--state-bind-address", default="0.0.0.0", help="local IPv4 address for state reception")
    parser.add_argument("--state-port", type=int, default=8871, help="state receive UDP port (default: 8871)")
    parser.add_argument(
        "--npc-state-port",
        type=int,
        default=8872,
        help="task NPC state receive UDP port (default: 8872)",
    )
    parser.add_argument("--gimbal-id", default="camera_gimbal")
    parser.add_argument("--frequency", type=float, default=20.0, help="renewal frequency in Hz")
    parser.add_argument("--speed-scale", type=float, default=1.0, help="direction input scale in (0, 1]")
    parser.add_argument(
        "--speed-mode",
        choices=("fine", "coarse"),
        default="fine",
        help="initial direction speed mode (default: fine)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.state_port == args.npc_state_port:
        raise SystemExit("state-port and npc-state-port must be different")
    if not 10.0 <= args.frequency <= 100.0:
        raise SystemExit("frequency must be in [10, 100] Hz")
    if not 0.0 < args.speed_scale <= 1.0:
        raise SystemExit("speed-scale must be in (0, 1]")
    try:
        sender = GimbalUdpSender(args.host, args.port, args.gimbal_id)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    except OSError as error:
        raise SystemExit(f"cannot create gimbal control UDP socket: {error}") from error
    try:
        state_receiver = GimbalStateReceiver(args.state_bind_address, args.state_port, args.gimbal_id)
    except ValueError as error:
        sender.close(send_stop=False)
        raise SystemExit(str(error)) from error
    except OSError as error:
        sender.close(send_stop=False)
        raise SystemExit(f"cannot bind state UDP {args.state_bind_address}:{args.state_port}: {error}") from error

    try:
        npc_state_receiver = NpcStateReceiver(args.state_bind_address, args.npc_state_port)
    except ValueError as error:
        state_receiver.close()
        sender.close(send_stop=False)
        raise SystemExit(str(error)) from error
    except OSError as error:
        state_receiver.close()
        sender.close(send_stop=False)
        raise SystemExit(
            f"cannot bind task NPC state UDP "
            f"{args.state_bind_address}:{args.npc_state_port}: {error}"
        ) from error

    # A valid protocol packet lets a remote UeSim instance learn this client's
    # state destination IP. This is a connectivity announcement, not a state query.
    try:
        sender.send("ping", {})
    except OSError as error:
        npc_state_receiver.close()
        state_receiver.close()
        sender.close(send_stop=False)
        raise SystemExit(f"cannot contact gimbal control endpoint: {error}") from error

    try:
        root = tk.Tk()
    except tk.TclError:
        npc_state_receiver.close()
        state_receiver.close()
        sender.close(send_stop=False)
        raise
    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass
    FourButtonGimbalUi(
        root,
        sender,
        state_receiver,
        npc_state_receiver,
        args.frequency,
        args.speed_scale,
        args.speed_mode,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
