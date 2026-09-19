"""Whisper transcription and Silero speech detection entirely on the PC."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import queue
import threading
import time
from typing import Callable
import wave

DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "faster-whisper-small"
SAMPLE_RATE = 16000
END_SILENCE_SECONDS = 1.0
VAD_INTERVAL_SECONDS = 0.3
# Retain quiet speech and the edges of words, including short negation words.
VAD_PARAMETERS = {
    "threshold": 0.45,
    "min_speech_duration_ms": 300,
    "min_silence_duration_ms": 1000,
    "speech_pad_ms": 150,
}


class SpeechError(Exception):
    pass


def _decode_pcm(pcm: bytes, sample_rate: int):
    """Resample native-rate mono PCM using Whisper's bundled PyAV converter.

    The short recording stays in memory. The proper resampler also removes
    frequencies above 8 kHz instead of aliasing them into the speech signal.
    """
    from faster_whisper.audio import decode_audio

    buffer = BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm)
    buffer.seek(0)
    return decode_audio(buffer, sampling_rate=SAMPLE_RATE)


def _speech_spans(audio):
    from faster_whisper.vad import get_speech_timestamps

    return get_speech_timestamps(audio, sampling_rate=SAMPLE_RATE, **VAD_PARAMETERS)


def _has_endpoint(audio, spans: list[dict]) -> bool:
    # An unfinished Silero segment ends at the current buffer boundary. Never
    # decode it; wait for a full second of silence after the last padded span.
    return bool(spans) and len(audio) - spans[-1]["end"] >= int(END_SILENCE_SECONDS * SAMPLE_RATE)


class OfflineRecognizer:
    def __init__(self, model_path: Path = DEFAULT_MODEL):
        self.model_path = Path(model_path)
        self._model = None
        self._lock = threading.Lock()

    def _load_model(self, on_event: Callable[[str, str], None]) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SpeechError("缺少 Whisper 語音套件，請先執行 setup.ps1") from exc
        if not all((self.model_path / name).is_file() for name in ("model.bin", "config.json", "tokenizer.json")):
            raise SpeechError("找不到完整的 Whisper 中文模型，請先執行 setup.ps1 或 download_model.py")
        on_event("state", "載入電腦上的 Whisper small 模型…")
        try:
            self._model = WhisperModel(
                str(self.model_path), device="cpu", compute_type="int8",
                cpu_threads=8, local_files_only=True,
            )
        except Exception as exc:
            raise SpeechError(f"無法載入本機 Whisper 模型：{exc}") from exc

    def _transcribe_audio(self, audio, stop: threading.Event, on_event: Callable[[str, str], None]) -> str | None:
        if stop.is_set():
            return None
        if not _speech_spans(audio):
            raise SpeechError("未偵測到完整語音，請靠近麥克風再試一次")
        if stop.is_set():
            return None
        on_event("state", "正在電腦上辨識整句語音，請稍候…")
        try:
            segments, _info = self._model.transcribe(
                audio, language="zh", beam_size=5, temperature=0,
                condition_on_previous_text=False, vad_filter=True,
                vad_parameters=VAD_PARAMETERS,
            )
            # Preserve the ENTIRE transcript. Selecting a command-shaped segment
            # could discard a later negation, question, or unrelated clause.
            parts = []
            for segment in segments:
                if stop.is_set():
                    return None
                parts.append(segment.text)
            if stop.is_set():
                return None
            text = "".join(parts).strip()
        except Exception as exc:
            if stop.is_set():
                return None
            raise SpeechError(f"離線語音辨識失敗：{exc}") from exc
        if not text:
            raise SpeechError("沒有辨識到完整語句，請再說一次")
        return text

    def transcribe_file(self, path: str | Path, stop: threading.Event | None = None) -> str | None:
        """Evaluate a local recording using the same unrestricted decoder as UI."""
        stop = stop if stop is not None else threading.Event()
        with self._lock:
            if stop.is_set():
                return None
            self._load_model(lambda *_event: None)
            if stop.is_set():
                return None
            from faster_whisper.audio import decode_audio

            audio = decode_audio(str(path), sampling_rate=SAMPLE_RATE)
            return self._transcribe_audio(audio, stop, lambda *_event: None)

    def listen_once(
        self,
        stop: threading.Event,
        on_event: Callable[[str, str], None],
        device: int | None = None,
        seconds: float = 12.0,
    ) -> str | None:
        """Record one complete utterance; timeout/cancellation never decode a fragment."""
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise SpeechError("缺少麥克風套件，請先執行 setup.ps1") from exc
        # A cancelled load/capture/decoder must release the microphone and model
        # before another request starts. Cancellation is checked after each stage.
        with self._lock:
            if stop.is_set():
                return None
            self._load_model(on_event)
            if stop.is_set():
                return None
            samplerate = int(sd.query_devices(device, "input")["default_samplerate"])
            chunks: queue.Queue[bytes] = queue.Queue(maxsize=150)
            audio_failed = threading.Event()

            def audio_callback(indata, _frames, _time_info, status):
                if status:
                    audio_failed.set()
                    return
                try:
                    chunks.put_nowait(bytes(indata))
                except queue.Full:
                    audio_failed.set()

            pcm = bytearray()
            next_scan_samples = max(1, int(samplerate * VAD_INTERVAL_SECONDS))
            scan_step = next_scan_samples
            max_samples = max(1, int(samplerate * seconds))
            completed_audio = None
            with sd.RawInputStream(
                samplerate=samplerate, blocksize=max(1, samplerate // 10),
                device=device, channels=1, dtype="int16", callback=audio_callback,
            ):
                if stop.is_set():
                    return None
                on_event("state", f"請說一句話，說完停頓約 1 秒（最多 {seconds:g} 秒）")
                deadline = time.monotonic() + seconds
                while not stop.is_set() and time.monotonic() < deadline:
                    if audio_failed.is_set():
                        raise SpeechError("麥克風資料中斷或處理不及，請重新辨識")
                    try:
                        chunk = chunks.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    pcm.extend(chunk)
                    samples = len(pcm) // 2
                    # Reaching the hard recording limit before an endpoint is
                    # established is a dropout, even if speech was detected.
                    if samples >= max_samples:
                        break
                    if samples < next_scan_samples:
                        continue
                    next_scan_samples = samples + scan_step
                    audio = _decode_pcm(bytes(pcm), samplerate)
                    spans = _speech_spans(audio)
                    if stop.is_set():
                        return None
                    if _has_endpoint(audio, spans):
                        completed_audio = audio
                        break
            if stop.is_set():
                return None
            if audio_failed.is_set():
                raise SpeechError("麥克風資料中斷或處理不及，請重新辨識")
            if completed_audio is None:
                raise SpeechError("未聽到完整語句或說話超時，請再按「開始辨識一句」重試")
            return self._transcribe_audio(completed_audio, stop, on_event)
