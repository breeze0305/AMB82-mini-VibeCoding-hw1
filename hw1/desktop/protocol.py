"""Small, synchronous AMB client. GUI workers call it without blocking Tk."""

from __future__ import annotations

import ipaddress
import json
import socket
import threading
import time
from dataclasses import dataclass

from commands import classify_sentence

PORT = 8266
COMMANDS = frozenset({"HELLO", "STATUS", "BLUE_ON", "GREEN_ON", "ALL_OFF"})
MAX_RESPONSE_BYTES = 2048


class CommunicationError(Exception):
    """Transport failed or the peer did not return a valid correlated reply."""


@dataclass(frozen=True)
class Reply:
    request_id: int
    command: str
    ok: bool
    blue: bool
    green: bool
    error: str = ""


def validate_reply(value: object, request_id: int, command: str) -> Reply:
    if not isinstance(value, dict):
        raise CommunicationError("AMB 回覆不是 JSON 物件")
    if value.get("device") != "AMB82-MINI":
        raise CommunicationError("連線目標不是 AMB82-MINI")
    if type(value.get("protocol")) is not int or value["protocol"] != 1:
        raise CommunicationError("AMB 通訊版本不相容")
    if type(value.get("id")) is not int or value["id"] != request_id:
        raise CommunicationError("AMB 回覆的指令編號不符")
    if value.get("command") != command:
        raise CommunicationError("AMB 回覆的指令不符")
    for key in ("ok", "blue", "green"):
        if type(value.get(key)) is not bool:
            raise CommunicationError(f"AMB 回覆缺少正確的 {key} 狀態")
    if "error" in value and not isinstance(value["error"], str):
        raise CommunicationError("AMB 錯誤訊息格式不正確")
    return Reply(request_id, command, value["ok"], value["blue"], value["green"], value.get("error", ""))


class AmbClient:
    """One connection, one in-flight request. Any framing/transport error closes it."""

    def __init__(self, timeout: float = 3.0, port: int = PORT):
        self.timeout = timeout
        self.port = port
        self._socket: socket.socket | None = None
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._next_id = 1
        self._ready = False

    @property
    def connected(self) -> bool:
        return self._ready

    def connect(self, host: str) -> Reply:
        try:
            address = str(ipaddress.IPv4Address(host.strip()))
        except ipaddress.AddressValueError as exc:
            raise CommunicationError("請輸入正確的 AMB IPv4 位址，例如 192.168.1.80") from exc
        with self._lock:
            self._close_unlocked()
            try:
                self._socket = socket.create_connection((address, self.port), timeout=self.timeout)
                self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                reply = self._exchange("HELLO")
                if not reply.ok:
                    raise CommunicationError(f"AMB 拒絕連線：{reply.error or 'HELLO 失敗'}")
                self._ready = True
                return reply
            except (OSError, CommunicationError) as exc:
                self._close_unlocked()
                if isinstance(exc, CommunicationError):
                    raise
                raise CommunicationError(f"無法連線至 {address}:{self.port}：{exc}") from exc

    def request(self, command: str) -> Reply:
        if command not in COMMANDS:
            raise ValueError(f"不支援的指令：{command}")
        with self._lock:
            if not self._ready:
                raise CommunicationError("尚未與 AMB 建立連線")
            try:
                return self._exchange(command)
            except (OSError, CommunicationError) as exc:
                self._close_unlocked()
                if isinstance(exc, CommunicationError):
                    raise
                raise CommunicationError(f"通訊失敗：{exc}") from exc

    def _exchange(self, command: str) -> Reply:
        assert self._socket is not None
        request_id = self._next_id
        self._next_id += 1
        payload = json.dumps({"id": request_id, "command": command}, separators=(",", ":"))
        deadline = time.monotonic() + self.timeout
        self._socket.settimeout(self.timeout)
        try:
            self._socket.sendall((payload + "\n").encode("utf-8"))
            while b"\n" not in self._buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise socket.timeout()
                self._socket.settimeout(remaining)
                chunk = self._socket.recv(1024)
                if not chunk:
                    raise CommunicationError("AMB 已中斷連線，未收到完整回覆")
                self._buffer.extend(chunk)
                if len(self._buffer) > MAX_RESPONSE_BYTES:
                    raise CommunicationError("AMB 回覆過長")
        except socket.timeout as exc:
            raise CommunicationError(f"{self.timeout:g} 秒內未收到 AMB 回覆；執行結果未知") from exc
        line, _, remainder = self._buffer.partition(b"\n")
        self._buffer = bytearray(remainder)
        # No unsolicited replies are part of this request/response protocol.
        if self._buffer:
            raise CommunicationError("AMB 傳回非預期的額外資料")
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommunicationError("AMB 回覆不是有效的 UTF-8 JSON") from exc
        return validate_reply(value, request_id, command)

    def _close_unlocked(self) -> None:
        self._ready = False
        if self._socket is not None:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._socket.close()
            self._socket = None
        self._buffer.clear()

    def close(self) -> None:
        with self._lock:
            self._close_unlocked()
