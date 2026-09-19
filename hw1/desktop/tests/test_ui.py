"""Regression checks for ACK-only display and late background-event safety."""
from pathlib import Path
import sys
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import AmbApp, Event
from protocol import Reply


class FakeClient:
    port = 8266

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class UiTests(unittest.TestCase):
    def setUp(self):
        self.window = tk.Tk()
        self.window.withdraw()
        with patch.object(AmbApp, "refresh_microphones"):
            self.app = AmbApp(self.window, initial_ip="127.0.0.1")
        self.app._background = lambda function: function()
        self.sent = []
        self.app._send = lambda command, **_kwargs: self.sent.append(command)

    def tearDown(self):
        self.app.close()

    def connect(self):
        self.app._process_event(Event(self.app.session, "connected", (FakeClient(), Reply(1, "HELLO", True, False, False))))

    def test_actions_disabled_before_handshake_and_no_partial_control(self):
        self.assertEqual(str(self.app.listen_button.cget("state")), "disabled")
        self.app.manual_command("BLUE_ON")
        self.assertEqual(self.sent, [])
        self.connect()
        self.app.listening = True
        self.app._process_event(Event(self.app.session, "speech_partial", "左邊開燈", self.app.speech_id))
        self.assertEqual(self.sent, [])
        self.app._process_event(Event(self.app.session, "speech_result", "左邊開燈", self.app.speech_id))
        self.assertEqual(self.sent, ["BLUE_ON"])

    def test_late_speech_from_old_connection_or_cancel_is_ignored(self):
        self.connect()
        old_session, old_speech = self.app.session, self.app.speech_id
        self.app.listening = True
        self.app.disconnect()
        self.connect()
        self.app._process_event(Event(old_session, "speech_result", "左邊開燈", old_speech))
        self.assertEqual(self.sent, [])
        self.app.listening = True
        old_speech = self.app.speech_id
        self.app.stop_voice()
        self.app._process_event(Event(self.app.session, "speech_result", "右邊開燈", old_speech))
        self.assertEqual(self.sent, [])

    def test_late_connect_is_closed_and_cannot_restore_cancelled_session(self):
        abandoned = FakeClient()
        self.app.disconnect()
        self.app._process_event(Event(self.app.session - 1, "connected", (abandoned, Reply(1, "HELLO", True, True, True))))
        self.assertTrue(abandoned.closed)
        self.assertFalse(self.app.connected)
        self.assertIn("未知", self.app.led_state.get())

    def test_failure_invalidates_leds_and_rejects_late_ack(self):
        self.connect()
        session = self.app.session
        self.app.action_busy = True
        self.app._process_event(Event(session, "failure", "等待回覆逾時"))
        self.app._process_event(Event(session, "reply", Reply(2, "BLUE_ON", True, True, False)))
        self.assertFalse(self.app.connected)
        self.assertIn("未知", self.app.led_state.get())
        self.assertNotIn("成功", self.app.transmission.get())
        self.assertEqual(str(self.app.listen_button.cget("state")), "disabled")

    def test_negative_ack_and_noncontrol_are_not_success(self):
        self.connect()
        self.app._process_event(Event(self.app.session, "reply", Reply(2, "BLUE_ON", False, False, False, "unsupported")))
        self.assertIn("拒絕", self.app.transmission.get())
        self.app._handle_sentence("不要左邊開燈")
        self.assertEqual(self.sent, [])
        self.assertIn("非控制", self.app.classification.get())

    def test_older_heartbeat_cannot_overwrite_new_command_snapshot(self):
        self.connect()
        self.app.heartbeat_busy = True
        self.app.action_busy = True
        self.app._process_event(Event(self.app.session, "reply", Reply(3, "BLUE_ON", True, True, False)))
        self.app._process_event(Event(self.app.session, "heartbeat", Reply(2, "STATUS", True, False, False)))
        self.assertIn("藍燈：亮", self.app.led_state.get())
        self.assertIn("成功", self.app.transmission.get())
        self.assertFalse(self.app.action_busy)
        self.assertFalse(self.app.heartbeat_busy)

    def test_phonetic_repair_preserves_raw_transcript_and_sends_right_command(self):
        self.connect()
        self.app._handle_sentence("有并开灯")
        self.assertEqual(self.sent, ["GREEN_ON"])
        self.assertEqual(self.app.transcript.get(), "有并开灯")
        self.assertIn("近音校正", self.app.classification.get())
        self.assertIn("右邊開燈", self.app.classification.get())
        self.assertNotIn("成功", self.app.transmission.get())

    def test_phonetic_repair_cannot_bypass_negation_or_connection_gate(self):
        self.app._handle_sentence("有并开灯")
        self.assertEqual(self.sent, [])
        self.assertIn("未連線", self.app.classification.get())
        self.connect()
        for phrase in ("不要有并开灯", "又边关灯", "右邊台燈", "有并开灯?"):
            with self.subTest(phrase=phrase):
                self.app._handle_sentence(phrase)
                self.assertEqual(self.sent, [])
                self.assertEqual(self.app.transcript.get(), phrase)
                self.assertIn("非控制", self.app.classification.get())
                self.assertIn("未傳送", self.app.transmission.get())


if __name__ == "__main__":
    unittest.main()
