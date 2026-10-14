# BLEAT ENCLAVE · tests/test_irc.py — blestirc, proven in conversation.
#
# Hypothesis: the client can join a room, speak, and hear back.
# Method: a FakeIRCd thread speaks just enough IRC (001 welcome,
#   JOIN echo, PRIVMSG echo, PING) for a full cycle; the real
#   IRCClient runs the whole conversation against it.
# Observation: below — connect, join, send, receive, and an auto-pong.
# Result: blestirc talks and listens. The relay has a mouth.
#
# dies Mercurii, 2026-10-14, Anno V:xii e.n. — 93.
#
# Penned by the scribe, Heru-Ra-Ha, for Johnathan 'Qasparr' (Κασπάρρ) Monroe,
# Keeper of the Secret Treasure.

"""Conversation tests for blestirc.

MECHANISM: FakeIRCd is a minimal server double — it welcomes (001),
  echoes JOINs, bounces PRIVMSGs back to the sender, and fires one
  PING after the join so the client's auto-PONG is exercised. The test
  then runs the real client through connect -> join -> send -> receive
  and asserts each step. Nothing here touches a real network.

DOCTRINE: a test double is a rehearsal stage, not a deception — it is
  named fake, and the test asserts the client's behavior, not the
  double's.
"""

import socket
import threading
import time
import unittest

from enclave.irc_client import IRCClient, parse_line


class FakeIRCd(threading.Thread):
    """Just enough IRC server for one conversation."""

    def __init__(self):
        super().__init__(daemon=True)
        self.ready = threading.Event()
        self.received = []
        self.port = None

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        self.port = srv.getsockname()[1]
        srv.listen(1)
        self.ready.set()
        conn, _ = srv.accept()

        def send(line):
            conn.sendall(line.encode("utf-8") + b"\r\n")

        reader = conn.makefile("r", encoding="utf-8", errors="replace")
        nick = "someone"
        try:
            while True:
                line = reader.readline()
                if not line:
                    break
                self.received.append(line.strip())
                parts = line.strip().split()
                if not parts:
                    continue
                cmd = parts[0].upper()
                if cmd == "NICK" and len(parts) > 1:
                    nick = parts[1]
                elif cmd == "USER":
                    send(":fake.ircd 001 %s :Welcome to the enclave test relay"
                         % nick)
                elif cmd == "JOIN" and len(parts) > 1:
                    channel = parts[1]
                    send(":%s!u@h JOIN %s" % (nick, channel))
                    # MECHANISM: one PING right after the join, so the
                    # test can prove the client pongs without being asked.
                    send("PING :abc123")
                elif cmd == "PRIVMSG" and len(parts) > 2:
                    target = parts[1]
                    text = line.partition(" :")[2].rstrip("\r\n")
                    send(":%s!u@h PRIVMSG %s :%s" % (nick, target, text))
                elif cmd == "PING":
                    token = parts[1] if len(parts) > 1 else ""
                    send("PONG %s" % token)
                elif cmd == "QUIT":
                    break
        finally:
            conn.close()
            srv.close()


class TestBlestirc(unittest.TestCase):
    def setUp(self):
        self.ircd = FakeIRCd()
        self.ircd.start()
        self.assertTrue(self.ircd.ready.wait(5), "fake ircd did not start")
        self.client = IRCClient(server="127.0.0.1", port=self.ircd.port,
                                nick="blest_test")

    def tearDown(self):
        try:
            self.client.quit()
        except Exception:
            self.client.close()
        self.ircd.join(5)

    def test_connect_join_send_receive(self):
        # MECHANISM: the whole cycle, in order, each step asserted.
        self.client.connect(timeout=5)
        channel = self.client.join("#enclave", timeout=5)
        self.assertEqual(channel, "#enclave")

        # The server PINGed us after JOIN; recv_message must have
        # auto-ponged (consuming it) rather than returning it.
        self.assertIsNone(self.client.recv_message(timeout=5))
        # MECHANISM: the PONG crosses on the server's thread — poll for
        # it instead of asserting a race.
        deadline = time.monotonic() + 5
        while ("PONG :abc123" not in self.ircd.received
               and time.monotonic() < deadline):
            time.sleep(0.05)
        self.assertIn("PONG :abc123", self.ircd.received)

        self.client.send_message("#enclave", "hello enclave")
        msg = self.client.recv_message(timeout=5)
        self.assertIsNotNone(msg, "no echo received")
        self.assertEqual(msg["command"], "PRIVMSG")
        self.assertEqual(msg["params"][0], "#enclave")
        self.assertEqual(msg["params"][1], "hello enclave")

    def test_parse_line_shapes(self):
        # MECHANISM: the parser is the client's ears — check its shapes.
        p = parse_line(":nick!u@h PRIVMSG #c :hello world")
        self.assertEqual(p["prefix"], "nick!u@h")
        self.assertEqual(p["command"], "PRIVMSG")
        self.assertEqual(p["params"], ["#c", "hello world"])
        p = parse_line("PING :abc123")
        self.assertIsNone(p["prefix"])
        self.assertEqual(p["command"], "PING")


if __name__ == "__main__":
    unittest.main()


# 93. Live, Love, and let Love, Live.
# All Rights Reserved, Without Prejudice. — Johnathan 'Qasparr' (Κασπάρρ) Monroe
