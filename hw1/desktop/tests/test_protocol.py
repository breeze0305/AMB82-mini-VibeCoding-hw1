import json
from pathlib import Path
import socket
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol import AmbClient, CommunicationError, classify_sentence, validate_reply


def response(request, **changes):
    value = dict(device="AMB82-MINI", protocol=1, id=request["id"], command=request["command"], ok=True, blue=False, green=False)
    value.update(changes)
    return value


class Peer:
    """Real loopback TCP peer, with configurable framing and failure behavior."""
    def __init__(self, handler):
        self.handler = handler
        self.requests = []
        self.error = None
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(2)
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            with self.listener.accept()[0] as connection:
                connection.settimeout(2)
                with connection.makefile("rb") as stream:
                    while line := stream.readline():
                        request = json.loads(line)
                        self.requests.append(request)
                        if self.handler(connection, request) is False:
                            break
        except (ConnectionError, OSError):
            pass
        except Exception as exc:
            self.error = exc
        finally:
            self.listener.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.listener.close()
        self.thread.join(timeout=3)
        if self.error:
            raise self.error


def send(connection, value):
    connection.sendall((json.dumps(value) + "\n").encode("utf-8"))


class ParserTests(unittest.TestCase):
    def test_exact_commands_with_chinese_variants_spacing_and_punctuation(self):
        for text in ("左邊開燈", "左边开灯", " 左 邊 開 燈。", "「左邊開燈」！"):
            with self.subTest(text=text):
                self.assertEqual(classify_sentence(text), "BLUE_ON")
        for text in ("右邊開燈", "右边开灯", "右 邊 开 灯，"):
            self.assertEqual(classify_sentence(text), "GREEN_ON")

    def test_negative_unrelated_extended_and_partial_text_never_controls(self):
        for text in ("", "今天天氣很好", "不要左邊開燈", "不要右邊開燈", "左邊開燈不要", "我說左邊開燈", "左邊", "左邊台燈", "右边台灯", "左邊開燈右邊開燈", "請說左邊開燈", "左邊開燈1", "左邊開燈💡"):
            with self.subTest(text=text):
                self.assertIsNone(classify_sentence(text))


class ValidationTests(unittest.TestCase):
    def test_rejects_spoofed_missing_malformed_and_uncorrelated_replies(self):
        valid = response({"id": 1, "command": "HELLO"})
        changes = (
            {"device": "other"}, {"protocol": True}, {"protocol": 2},
            {"id": True}, {"id": "1"}, {"id": 2}, {"command": "BLUE_ON"},
            {"ok": 1}, {"blue": "false"}, {"green": 0}, {"error": []},
        )
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(CommunicationError):
                    validate_reply({**valid, **change}, 1, "HELLO")
        for missing in ("device", "protocol", "id", "command", "ok", "blue", "green"):
            malformed = valid.copy()
            del malformed[missing]
            with self.assertRaises(CommunicationError):
                validate_reply(malformed, 1, "HELLO")


class ClientTests(unittest.TestCase):
    def test_no_commands_before_handshake(self):
        client = AmbClient()
        with self.assertRaises(CommunicationError):
            client.request("BLUE_ON")
        for host in ("", "http://192.168.1.2", "not-a-host", "192.168.1.999"):
            with self.assertRaises(CommunicationError):
                client.connect(host)

    def test_hello_and_commands_share_one_connection_and_correlate(self):
        state = dict(blue=False, green=False)

        def handler(connection, request):
            if request["command"] == "BLUE_ON":
                state["blue"] = True
            elif request["command"] == "GREEN_ON":
                state["green"] = True
            elif request["command"] == "ALL_OFF":
                state.update(blue=False, green=False)
            send(connection, response(request, **state))

        with Peer(handler) as peer:
            client = AmbClient(port=peer.port)
            try:
                self.assertFalse(client.connect("127.0.0.1").blue)
                self.assertTrue(client.connected)
                self.assertTrue(client.request("BLUE_ON").blue)
                reply = client.request("GREEN_ON")
                self.assertTrue(reply.blue and reply.green)
                self.assertTrue(client.request("STATUS").green)
                self.assertFalse(client.request("ALL_OFF").green)
                self.assertEqual([r["id"] for r in peer.requests], [1, 2, 3, 4, 5])
                self.assertEqual(peer.requests[0]["command"], "HELLO")
            finally:
                client.close()

    def test_fragmented_utf8_ack_is_reassembled(self):
        def handler(connection, request):
            data = (json.dumps(response(request, error="測試"), ensure_ascii=False) + "\n").encode()
            for index in range(0, len(data), 3):
                connection.sendall(data[index:index + 3])

        with Peer(handler) as peer:
            client = AmbClient(port=peer.port)
            try:
                self.assertEqual(client.connect("127.0.0.1").error, "測試")
            finally:
                client.close()

    def test_negative_ack_is_not_success_and_does_not_lose_connection(self):
        def handler(connection, request):
            send(connection, response(request, ok=request["command"] != "BLUE_ON", error="rejected"))

        with Peer(handler) as peer:
            client = AmbClient(port=peer.port)
            try:
                client.connect("127.0.0.1")
                self.assertFalse(client.request("BLUE_ON").ok)
                self.assertTrue(client.connected)
                self.assertTrue(client.request("STATUS").ok)
            finally:
                client.close()

    def test_handshake_rejection_prevents_connected_state(self):
        with Peer(lambda conn, req: send(conn, response(req, ok=False, error="busy"))) as peer:
            client = AmbClient(port=peer.port)
            with self.assertRaises(CommunicationError):
                client.connect("127.0.0.1")
            self.assertFalse(client.connected)

    def test_bad_reply_and_closed_peer_invalidate_connection(self):
        for broken in (b"not json\n", b"\xff\n", b"x" * 2200, b"{}\n", b"{}\n{}\n", b""):
            with self.subTest(reply=broken[:20]):
                def handler(connection, request):
                    if request["command"] == "HELLO":
                        send(connection, response(request))
                    else:
                        if broken:
                            connection.sendall(broken)
                        return False
                with Peer(handler) as peer:
                    client = AmbClient(port=peer.port)
                    client.connect("127.0.0.1")
                    with self.assertRaises(CommunicationError):
                        client.request("BLUE_ON")
                    self.assertFalse(client.connected)

    def test_trickling_response_cannot_extend_total_timeout(self):
        def handler(connection, request):
            if request["command"] == "HELLO":
                send(connection, response(request))
            else:
                for _ in range(20):
                    connection.sendall(b" ")
                    time.sleep(0.03)
        with Peer(handler) as peer:
            client = AmbClient(timeout=0.12, port=peer.port)
            client.connect("127.0.0.1")
            started = time.monotonic()
            with self.assertRaisesRegex(CommunicationError, "執行結果未知"):
                client.request("GREEN_ON")
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertFalse(client.connected)

    def test_parallel_requests_remain_serialized(self):
        with Peer(lambda conn, req: send(conn, response(req))) as peer:
            client = AmbClient(port=peer.port)
            client.connect("127.0.0.1")
            errors = []
            def work(command):
                try:
                    client.request(command)
                except Exception as exc:
                    errors.append(exc)
            threads = [threading.Thread(target=work, args=(cmd,)) for cmd in ("STATUS", "BLUE_ON", "GREEN_ON")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            client.close()
            self.assertFalse(errors)
            self.assertEqual([r["id"] for r in peer.requests], [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
