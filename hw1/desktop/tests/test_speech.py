"""Capture/decode boundaries without opening the user's microphone."""

from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speech import OfflineRecognizer, SpeechError, SAMPLE_RATE, _decode_pcm, _has_endpoint


class SpeechTests(unittest.TestCase):
    def run_capture(
        self, *, chunks_count=35, voiced_chunks=10, audio_error=False,
        cancel_on_open=False, cancel_during_decode=False, cancel_after_decode=False,
        transcript=("右边开灯",), seconds=12, rate=48000,
    ):
        """Drive capture with native-rate PCM and deterministic speech spans.

        Only speech detection/Whisper inference are replaced; PCM resampling,
        queuing, endpoint detection, cancellation and full-text assembly run.
        """
        stop = threading.Event()
        events = []
        streams = []
        callback_count = []
        model = Mock()

        def transcribe(audio, **options):
            model.captured_audio = audio.copy()
            if cancel_during_decode:
                stop.set()

            def segments():
                for text in transcript:
                    yield SimpleNamespace(text=text)
                if cancel_after_decode:
                    stop.set()
            return segments(), SimpleNamespace()

        model.transcribe.side_effect = transcribe

        class Stream:
            def __init__(self, **kwargs):
                self.callback = kwargs["callback"]
                self.options = kwargs
                self.closed = False
                streams.append(self)

            def __enter__(self):
                if cancel_on_open:
                    stop.set()
                frames = rate // 10
                samples = np.arange(frames)
                voice = (2000 * np.sin(2 * np.pi * 220 * samples / rate)).astype(np.int16).tobytes()
                silence = np.zeros(frames, dtype=np.int16).tobytes()
                for index in range(chunks_count):
                    self.callback(voice if index < voiced_chunks else silence, frames, None, audio_error)
                    callback_count.append(index)
                return self

            def __exit__(self, *_args):
                self.closed = True

        def speech_spans(audio):
            # A stand-in for Silero that finds our synthetic voiced PCM. Keeping
            # this independent of elapsed time catches native/16 kHz mixups.
            indices = np.flatnonzero(np.abs(audio) > 0.01)
            if len(indices) < 0.2 * SAMPLE_RATE:
                return []
            return [{"start": int(indices[0]), "end": int(indices[-1]) + 1}]

        sd = SimpleNamespace(query_devices=lambda _device, _kind: {"default_samplerate": rate}, RawInputStream=Stream)
        recognizer = OfflineRecognizer()
        recognizer._model = model
        with patch.dict(sys.modules, sounddevice=sd), patch("speech._speech_spans", side_effect=speech_spans):
            text = recognizer.listen_once(stop, lambda *event: events.append(event), seconds=seconds, device=7)
        return text, events, model, streams

    def test_native_rate_capture_resamples_and_waits_for_sentence_endpoint(self):
        text, events, model, streams = self.run_capture()
        self.assertEqual(text, "右边开灯")
        self.assertEqual(streams[0].options["samplerate"], 48000)
        self.assertEqual(streams[0].options["channels"], 1)
        self.assertEqual(streams[0].options["dtype"], "int16")
        self.assertTrue(streams[0].closed)
        self.assertGreaterEqual(len(model.captured_audio), 2 * SAMPLE_RATE)
        self.assertLess(len(model.captured_audio), 3 * SAMPLE_RATE)
        self.assertFalse(any(kind == "partial" for kind, _text in events))

    def test_entire_transcript_preserves_later_negation_and_unrelated_words(self):
        for segments in (("右边开灯", "，不要。"), ("不要", "右边开灯"), ("今天", "天氣很好")):
            with self.subTest(segments=segments):
                text, _events, model, _streams = self.run_capture(transcript=segments)
                self.assertEqual(text, "".join(segments))
                options = model.transcribe.call_args.kwargs
                self.assertEqual(options["language"], "zh")
                self.assertEqual(options["temperature"], 0)
                self.assertFalse(options["condition_on_previous_text"])
                self.assertTrue(options["vad_filter"])
                self.assertNotIn("initial_prompt", options)
                self.assertNotIn("hotwords", options)
                self.assertNotIn("prefix", options)

    def test_cancel_during_capture_never_returns_text(self):
        text, _events, model, streams = self.run_capture(cancel_on_open=True)
        self.assertIsNone(text)
        model.transcribe.assert_not_called()
        self.assertTrue(streams[0].closed)

    def test_cancel_during_or_after_decoding_never_returns_text(self):
        for option in ("cancel_during_decode", "cancel_after_decode"):
            with self.subTest(option=option):
                text, _events, _model, streams = self.run_capture(**{option: True})
                self.assertIsNone(text)
                self.assertTrue(streams[0].closed)

    def test_audio_drop_is_error_instead_of_partial_command(self):
        with self.assertRaisesRegex(SpeechError, "資料中斷"):
            self.run_capture(audio_error=True)

    def test_ongoing_speech_at_capture_limit_never_reaches_decoder(self):
        with patch.object(OfflineRecognizer, "_transcribe_audio") as decode:
            with self.assertRaisesRegex(SpeechError, "完整語句"):
                self.run_capture(chunks_count=30, voiced_chunks=30, seconds=3)
            decode.assert_not_called()

    def test_silent_recording_at_capture_limit_never_reaches_decoder(self):
        with patch.object(OfflineRecognizer, "_transcribe_audio") as decode:
            with self.assertRaisesRegex(SpeechError, "完整語句"):
                self.run_capture(chunks_count=30, voiced_chunks=0, seconds=3)
            decode.assert_not_called()

    def test_missing_microphone_frames_eventually_timeout(self):
        with patch.object(OfflineRecognizer, "_transcribe_audio") as decode:
            with self.assertRaisesRegex(SpeechError, "完整語句"):
                self.run_capture(chunks_count=0, seconds=0.01)
            decode.assert_not_called()

    def test_actual_silero_rejects_silence_before_whisper_can_hallucinate(self):
        recognizer = OfflineRecognizer()
        recognizer._model = Mock()
        with self.assertRaisesRegex(SpeechError, "未偵測到"):
            recognizer._transcribe_audio(np.zeros(2 * SAMPLE_RATE, dtype=np.float32), threading.Event(), lambda *_args: None)
        recognizer._model.transcribe.assert_not_called()

    def test_endpoint_requires_full_silence_after_last_speech(self):
        audio = np.zeros(3 * SAMPLE_RATE, dtype=np.float32)
        self.assertFalse(_has_endpoint(audio, []))
        self.assertFalse(_has_endpoint(audio, [{"start": 0, "end": len(audio)}]))
        self.assertFalse(_has_endpoint(audio, [{"start": 0, "end": 2 * SAMPLE_RATE + 1}]))
        self.assertTrue(_has_endpoint(audio, [{"start": 0, "end": 2 * SAMPLE_RATE}]))
        self.assertFalse(_has_endpoint(audio, [{"start": 0, "end": SAMPLE_RATE}, {"start": 2 * SAMPLE_RATE, "end": len(audio)}]))

    def test_resampling_preserves_quiet_audio_without_amplitude_gate(self):
        rate = 48000
        samples = np.arange(rate)
        pcm = (200 * np.sin(2 * np.pi * 300 * samples / rate)).astype(np.int16).tobytes()
        audio = _decode_pcm(pcm, rate)
        self.assertEqual(len(audio), SAMPLE_RATE)
        self.assertEqual(audio.dtype, np.float32)
        self.assertGreater(float(np.sqrt(np.mean(audio ** 2))), 0.003)

    def test_model_is_loaded_from_local_files_only_with_cpu_int8(self):
        recognizer = OfflineRecognizer()
        with patch("faster_whisper.WhisperModel") as model, patch.object(Path, "is_file", return_value=True):
            recognizer._load_model(lambda *_args: None)
            recognizer._load_model(lambda *_args: None)
        model.assert_called_once()
        self.assertEqual(model.call_args.kwargs, {
            "device": "cpu", "compute_type": "int8", "cpu_threads": 8, "local_files_only": True,
        })

    def test_incomplete_model_has_setup_instructions(self):
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(SpeechError, "setup.ps1"):
                OfflineRecognizer()._load_model(lambda *_args: None)

    def test_cancel_before_loading_never_opens_microphone(self):
        stop = threading.Event()
        stop.set()
        recognizer = OfflineRecognizer()
        with patch.object(recognizer, "_load_model") as load:
            self.assertIsNone(recognizer.listen_once(stop, lambda *_args: None))
        load.assert_not_called()

    def test_cancel_after_model_load_never_opens_microphone(self):
        stop = threading.Event()
        recognizer = OfflineRecognizer()
        with patch.object(recognizer, "_load_model", side_effect=lambda _event: stop.set()), patch("sounddevice.RawInputStream") as stream:
            self.assertIsNone(recognizer.listen_once(stop, lambda *_args: None))
        stream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
