"""Run with: python app.py. Only this module owns/updates Tk widgets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from commands import interpret_sentence
from protocol import AmbClient, CommunicationError, Reply
from speech import DEFAULT_MODEL, OfflineRecognizer


@dataclass
class Event:
    session: int
    kind: str
    data: object
    speech_id: int = 0


class AmbApp:
    def __init__(self, window: tk.Tk, model_path: Path = DEFAULT_MODEL, initial_ip: str = "", device: int | None = None):
        self.window = window
        self.events: queue.Queue[Event] = queue.Queue()
        self.session = 0
        self.session_cancel = threading.Event()
        self.speech_id = 0
        self.speech_stop: threading.Event | None = None
        self.client: AmbClient | None = None
        self.connecting = False
        self.connected = False
        self.action_busy = False
        self.heartbeat_busy = False
        self.listening = False
        self.closed = False
        self.last_heartbeat = time.monotonic()
        self.last_reply_id = 0
        self.recognizer = OfflineRecognizer(model_path)
        self.device = device

        window.title("AMB82-MINI 語音燈光控制")
        window.geometry("840x800")
        window.minsize(760, 760)
        window.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TLabel", font=("Microsoft JhengHei UI", 11))
        style.configure("TButton", font=("Microsoft JhengHei UI", 10), padding=(10, 5))
        style.configure("Title.TLabel", font=("Microsoft JhengHei UI", 21, "bold"))
        style.configure("Hint.TLabel", foreground="#596579", font=("Microsoft JhengHei UI", 10))

        self.ip = tk.StringVar(value=initial_ip)
        self.connection = tk.StringVar(value="尚未連線")
        self.voice_state = tk.StringVar(value="連線成功後，按按鈕辨識一句話")
        self.transcript = tk.StringVar(value="尚未辨識")
        self.classification = tk.StringVar(value="等待語句")
        self.transmission = tk.StringVar(value="尚未傳送")
        self.communication = tk.StringVar(value="尚未建立通訊")
        self.led_state = tk.StringVar(value="藍燈：未知    綠燈：未知")
        self.typed_sentence = tk.StringVar()
        self.microphone = tk.StringVar(value="系統預設麥克風")
        self.microphone_ids: list[int | None] = [None]

        outer = ttk.Frame(window, padding=22)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(6, weight=1)
        ttk.Label(outer, text="語音燈光控制", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(outer, text="Whisper small 本機中文辨識 · AMB 接收指令並回傳燈光狀態", style="Hint.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 17))

        network = ttk.LabelFrame(outer, text="1. 連接開發板", padding=12)
        network.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        network.columnconfigure(1, weight=1)
        ttk.Label(network, text="AMB IP").grid(row=0, column=0, padx=(0, 9))
        self.ip_entry = ttk.Entry(network, textvariable=self.ip, width=22, font=("Consolas", 12))
        self.ip_entry.grid(row=0, column=1, sticky="ew")
        self.connect_button = ttk.Button(network, text="連線", command=self.connect)
        self.connect_button.grid(row=0, column=2, padx=(9, 0))
        self.disconnect_button = ttk.Button(network, text="中斷連線", command=self.disconnect)
        self.disconnect_button.grid(row=0, column=3, padx=(8, 0))
        ttk.Label(network, textvariable=self.connection).grid(row=1, column=0, columnspan=4, sticky="w", pady=(9, 0))

        voice = ttk.LabelFrame(outer, text="2. 說出指令", padding=12)
        voice.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        voice.columnconfigure(2, weight=1)
        self.listen_button = ttk.Button(voice, text="開始辨識一句", command=self.start_voice)
        self.listen_button.grid(row=0, column=0)
        self.stop_button = ttk.Button(voice, text="取消辨識", command=self.stop_voice)
        self.stop_button.grid(row=0, column=1, padx=8)
        ttk.Label(voice, text="「左邊開燈」／「右邊開燈」", style="Hint.TLabel").grid(row=0, column=2, sticky="w")
        mic_row = ttk.Frame(voice)
        mic_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        mic_row.columnconfigure(1, weight=1)
        ttk.Label(mic_row, text="麥克風", style="Hint.TLabel").grid(row=0, column=0, padx=(0, 9))
        self.microphone_combo = ttk.Combobox(mic_row, textvariable=self.microphone, state="readonly", width=48)
        self.microphone_combo.grid(row=0, column=1, sticky="ew")
        self.refresh_mics_button = ttk.Button(mic_row, text="重新整理", command=self.refresh_microphones)
        self.refresh_mics_button.grid(row=0, column=2, padx=(8, 0))
        ttk.Label(voice, textvariable=self.voice_state, wraplength=720).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        result = ttk.LabelFrame(outer, text="3. 辨識與傳輸結果", padding=12)
        result.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        result.columnconfigure(1, weight=1)
        for row, (title, value) in enumerate((
            ("辨識文字", self.transcript), ("語句判斷", self.classification),
            ("傳輸結果", self.transmission), ("通訊狀態", self.communication),
            ("板端回報", self.led_state),
        )):
            ttk.Label(result, text=title, style="Hint.TLabel").grid(row=row, column=0, sticky="nw", padx=(0, 16), pady=4)
            ttk.Label(result, textvariable=value, wraplength=625).grid(row=row, column=1, sticky="w", pady=4)

        manual = ttk.LabelFrame(outer, text="手動測試", padding=12)
        manual.grid(row=5, column=0, sticky="ew", pady=(0, 12))
        manual.columnconfigure(0, weight=1)
        buttons = ttk.Frame(manual)
        buttons.grid(row=0, column=0, columnspan=2, sticky="w")
        self.manual_buttons = []
        for text, command in (("左邊／藍燈開", "BLUE_ON"), ("右邊／綠燈開", "GREEN_ON"), ("全部關燈", "ALL_OFF")):
            button = ttk.Button(buttons, text=text, command=lambda cmd=command: self.manual_command(cmd))
            button.pack(side="left", padx=(0, 8))
            self.manual_buttons.append(button)
        self.text_entry = ttk.Entry(manual, textvariable=self.typed_sentence, font=("Microsoft JhengHei UI", 11))
        self.text_entry.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.text_entry.bind("<Return>", lambda _event: self.submit_text())
        self.text_button = ttk.Button(manual, text="輸入語句測試", command=self.submit_text)
        self.text_button.grid(row=1, column=1, padx=(8, 0), pady=(10, 0))

        self.log = ScrolledText(outer, height=4, state="disabled", wrap="word", font=("Microsoft JhengHei UI", 9), background="#f5f7fb", relief="flat")
        self.log.grid(row=6, column=0, sticky="nsew")
        self._log("先讓電腦與 AMB 在同一網路，再輸入 AMB 的 IP 並連線。")
        self.refresh_microphones()
        self._refresh_controls()
        self.window.after(80, self._poll)

    @staticmethod
    def _background(function) -> None:
        threading.Thread(target=function, daemon=True).start()

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"{datetime.now():%H:%M:%S}  {message}\n")
        # Keep prolonged use bounded without writing transcripts/audio to disk.
        if int(self.log.index("end-1c").split(".")[0]) > 300:
            self.log.delete("1.0", "51.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _refresh_controls(self) -> None:
        ready = self.connected and not self.action_busy and not self.listening
        self.connect_button.configure(state="disabled" if self.connected or self.connecting else "normal")
        self.ip_entry.configure(state="disabled" if self.connected or self.connecting else "normal")
        self.disconnect_button.configure(state="normal" if self.connected or self.connecting else "disabled")
        self.listen_button.configure(state="normal" if ready else "disabled")
        self.stop_button.configure(state="normal" if self.listening else "disabled")
        self.microphone_combo.configure(state="disabled" if self.listening else "readonly")
        self.refresh_mics_button.configure(state="disabled" if self.listening else "normal")
        for button in (*self.manual_buttons, self.text_button, self.text_entry):
            button.configure(state="normal" if ready else "disabled")

    def refresh_microphones(self) -> None:
        previous = self.microphone_combo.current()
        selected = self.microphone_ids[previous] if previous >= 0 else self.device
        labels = ["系統預設麥克風"]
        ids: list[int | None] = [None]
        try:
            import sounddevice as sd
            hosts = sd.query_hostapis()
            for index, info in enumerate(sd.query_devices()):
                if info["max_input_channels"] > 0:
                    ids.append(index)
                    labels.append(f"{index}: {info['name']} [{hosts[info['hostapi']]['name']}]")
        except Exception as exc:
            self._log(f"無法列出麥克風：{exc}；可先測試文字與手動控制。")
        self.microphone_ids = ids
        self.microphone_combo.configure(values=labels)
        self.microphone_combo.current(ids.index(selected) if selected in ids else 0)

    def connect(self) -> None:
        if self.connected or self.connecting:
            return
        host = self.ip.get().strip()
        self.session += 1
        session = self.session
        self.last_reply_id = 0
        self.session_cancel = threading.Event()
        cancelled = self.session_cancel
        self.connecting = True
        self.connection.set(f"正在連接 {host}…")
        self.communication.set("等待 AMB 身分與版本確認")
        self.transmission.set("尚未傳送控制指令")
        self._refresh_controls()

        def work():
            client = AmbClient()
            try:
                reply = client.connect(host)
                if cancelled.is_set():
                    client.close()
                    return
                self.events.put(Event(session, "connected", (client, reply)))
            except Exception as exc:
                client.close()
                self.events.put(Event(session, "failure", str(exc)))

        self._background(work)

    def _invalidate_session(self) -> None:
        self.session_cancel.set()
        self.session += 1
        self.stop_voice(quiet=True)
        client, self.client = self.client, None
        self.connected = self.connecting = self.action_busy = self.heartbeat_busy = False
        self.led_state.set("藍燈：未知    綠燈：未知")
        if client is not None:
            self._background(client.close)
        self._refresh_controls()

    def disconnect(self) -> None:
        pending = self.action_busy
        self._invalidate_session()
        self.connection.set("已中斷連線")
        self.communication.set("未連線；開發板可能保留最後一次燈光狀態")
        self.transmission.set("連線已中斷；最後指令執行結果未知" if pending else "未連線，不傳送指令")
        self.voice_state.set("連線成功後，按按鈕辨識一句話")
        self._log("已中斷連線。")

    def _fail(self, message: str) -> None:
        self._invalidate_session()
        self.connection.set("通訊失敗，請檢查 AMB IP 與網路後重新連線")
        self.communication.set(message)
        self.transmission.set("無法確認 AMB 執行結果")
        self.voice_state.set("辨識已停止；重新連線後再操作")
        self._log(f"通訊失敗：{message}")

    def _update_leds(self, reply: Reply) -> None:
        self.led_state.set(f"藍燈：{'亮' if reply.blue else '滅'}    綠燈：{'亮' if reply.green else '滅'}（依板端回覆）")

    def _send(self, command: str, heartbeat: bool = False) -> None:
        if not self.connected or self.client is None:
            return
        if not heartbeat and self.action_busy:
            self.transmission.set("上一筆指令尚在等待回覆，請稍後重試")
            return
        session, client, cancelled = self.session, self.client, self.session_cancel
        if heartbeat:
            self.heartbeat_busy = True
        else:
            self.action_busy = True
            self.transmission.set(f"傳送 {command}，等待 AMB 回覆…")
            self._log(f"送出 {command}，等待確認。")
        self._refresh_controls()

        def work():
            if cancelled.is_set():
                return
            try:
                reply = client.request(command)
                self.events.put(Event(session, "heartbeat" if heartbeat else "reply", reply))
            except Exception as exc:
                self.events.put(Event(session, "failure", str(exc)))

        self._background(work)

    def manual_command(self, command: str) -> None:
        if not self.connected or self.action_busy or self.listening:
            return
        self.transcript.set("（手動按鈕）")
        self.classification.set(f"手動控制：{command}")
        self._send(command)

    def submit_text(self) -> None:
        if self.connected and not self.action_busy and not self.listening:
            self._handle_sentence(self.typed_sentence.get(), source="文字測試")

    def _handle_sentence(self, text: str, source: str = "語音") -> None:
        self.transcript.set(text or "（沒有文字）")
        match = interpret_sentence(text)
        command = match.command
        self._log(f"{source}：{text or '（沒有文字）'}")
        if command is None:
            self.classification.set(f"非控制指令：{match.reason}")
            self.transmission.set("未傳送，不改變 LED")
        elif self.connected:
            label = "近音校正" if match.method == "phonetic" else "指定控制語句"
            self.classification.set(f"{label} → {match.phrase}（{command}）")
            self._send(command)
        else:
            self.classification.set(f"{match.phrase}，但目前未連線")
            self.transmission.set("未傳送：請先連接 AMB")

    def start_voice(self) -> None:
        if not self.connected or self.action_busy or self.listening:
            return
        self.speech_id += 1
        speech_id, session = self.speech_id, self.session
        stop = threading.Event()
        self.speech_stop = stop
        device_index = self.microphone_combo.current()
        device = self.microphone_ids[device_index] if device_index >= 0 else None
        self.listening = True
        self.transcript.set("等待說話…")
        self.classification.set("辨識中，尚未判斷")
        self.transmission.set("尚未傳送，等待完整辨識結果")
        self.voice_state.set("準備麥克風…")
        self._refresh_controls()

        def emit(kind: str, data: str):
            self.events.put(Event(session, f"speech_{kind}", data, speech_id))

        def work():
            try:
                text = self.recognizer.listen_once(stop, emit, device=device)
                if text is not None and not stop.is_set():
                    emit("result", text)
            except Exception as exc:
                if not stop.is_set():
                    emit("error", str(exc))

        self._background(work)

    def stop_voice(self, quiet: bool = False) -> None:
        self.speech_id += 1
        if self.speech_stop is not None:
            self.speech_stop.set()
            self.speech_stop = None
        was_listening = self.listening
        self.listening = False
        if was_listening and not quiet:
            self.voice_state.set("已取消辨識，未傳送任何語音指令")
            self.classification.set("辨識已取消")
            self.transmission.set("未傳送")
        self._refresh_controls()

    def _process_event(self, event: Event) -> None:
        if event.session != self.session or self.closed:
            if event.kind == "connected":
                self._background(event.data[0].close)
            return
        if event.kind.startswith("speech_"):
            if event.speech_id != self.speech_id or not self.listening:
                return
            if event.kind == "speech_state":
                self.voice_state.set(event.data)
            elif event.kind == "speech_partial":
                self.transcript.set(f"{event.data}（辨識中）")
            elif event.kind in {"speech_result", "speech_error"}:
                self.listening = False
                self.speech_stop = None
                if event.kind == "speech_result":
                    self.voice_state.set("辨識完成；再按按鈕可辨識下一句")
                    self._handle_sentence(event.data)
                else:
                    self.voice_state.set(f"辨識失敗：{event.data}")
                    self.classification.set("無法判斷，請重試")
                    self.transmission.set("未傳送任何語音指令")
                    self._log(f"辨識失敗：{event.data}")
                self._refresh_controls()
            return
        if event.kind == "connected":
            self.client, reply = event.data
            self.connected, self.connecting = True, False
            self.last_heartbeat = time.monotonic()
            self.last_reply_id = reply.request_id
            self.connection.set(f"已連線至 {self.ip.get().strip()}:{self.client.port} · AMB82-MINI")
            self.communication.set("正常，已收到 AMB 連線確認")
            self.voice_state.set("按「開始辨識一句」，說完請停頓一下")
            self._update_leds(reply)
            self._log("AMB 身分與通訊版本確認成功，可以開始操作。")
        elif event.kind == "failure":
            self._fail(event.data)
        elif event.kind in {"reply", "heartbeat"}:
            reply = event.data
            newest = reply.request_id > self.last_reply_id
            if newest:
                self.last_reply_id = reply.request_id
                self._update_leds(reply)
                self.last_heartbeat = time.monotonic()
                self.communication.set(f"正常，最後收到板端回覆 {datetime.now():%H:%M:%S}")
            if event.kind == "heartbeat":
                self.heartbeat_busy = False
                if newest and not reply.ok:
                    self._fail(f"AMB 狀態查詢失敗：{reply.error}")
            else:
                self.action_busy = False
                if reply.ok:
                    self.transmission.set(f"成功：AMB 已確認執行 {reply.command}（編號 {reply.request_id}）")
                else:
                    self.transmission.set(f"AMB 拒絕指令：{reply.error or reply.command}")
                self._log(self.transmission.get())
        self._refresh_controls()

    def _poll(self) -> None:
        if self.closed:
            return
        try:
            while True:
                self._process_event(self.events.get_nowait())
        except queue.Empty:
            pass
        if self.connected and not self.action_busy and not self.heartbeat_busy and time.monotonic() - self.last_heartbeat >= 5:
            self._send("STATUS", heartbeat=True)
        self.window.after(80, self._poll)

    def close(self) -> None:
        self.closed = True
        self._invalidate_session()
        self.window.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="AMB82-MINI 本機語音控制桌面程式")
    parser.add_argument("--ip", default="", help="預填 AMB IPv4 位址；仍須手動按連線")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="本機 faster-whisper 模型目錄")
    parser.add_argument("--device", type=int, help="sounddevice 麥克風編號；預設使用系統預設輸入")
    args = parser.parse_args()
    window = tk.Tk()
    AmbApp(window, model_path=args.model, initial_ip=args.ip, device=args.device)
    window.mainloop()


if __name__ == "__main__":
    main()
