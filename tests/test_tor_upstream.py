# BLEAT ENCLAVE · tests/test_tor_upstream.py — the dormant road, honestly tested.
#
# Hypothesis: the Tor upstream refuses live use without Tor, yet its
#   handshake code is genuinely correct.
# Method: assert DORMANT and the refusal; then run the real handshake
#   bytes against a mock SOCKS5 speaker via the test-only _connect
#   injection, with a canned DNS answer on the far end.
# Observation: the refusal raises; the mock completes; the answer parses.
# Result: proven code, honest dormancy — never a faked live connection.
#
# dies Mercurii, 2026-10-14, Anno V:xii e.n. — 93.
#
# Penned by the scribe, Heru-Ra-Ha, for Johnathan 'Qasparr' (Κασπάρρ) Monroe,
# Keeper of the Secret Treasure.

"""Tests for the (dormant) Tor upstream.

MECHANISM: two halves. First, the honesty half — DORMANT must be True
  on this host and a live resolve() must raise TorDormantError. Second,
  the correctness half — a FakeSocks5 thread speaks just enough RFC 1928
  to complete the handshake, then answers the DNS-over-TCP query with a
  canned A record; the test injects it via _connect so the production
  handshake code runs unmodified.

DOCTRINE: the mock proves the code; it never pretends to be Tor.
"""

import socket
import struct
import threading
import unittest

from dnslib import DNSRecord, QTYPE, RR, A

from enclave import tor_upstream


def _recvn(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise RuntimeError("mock: connection closed")
        buf += chunk
    return buf


class FakeSocks5(threading.Thread):
    """A test double that speaks handshake + one DNS answer.

    MECHANISM: accepts one connection, performs the no-auth SOCKS5
      greeting and a CONNECT for a domain-name address, then reads a
      length-prefixed DNS query and answers it with 93.184.216.34.
      Asserts the client's bytes match the RFC — a wrong handshake
      fails the test, not the mock.
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.ready = threading.Event()
        self.port = None

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        self.port = srv.getsockname()[1]
        srv.listen(1)
        self.ready.set()
        conn, _ = srv.accept()
        try:
            assert _recvn(conn, 3) == b"\x05\x01\x00", "bad greeting"
            conn.sendall(b"\x05\x00")  # no auth accepted
            ver, cmd, _, atyp = _recvn(conn, 4)
            assert (ver, cmd, atyp) == (5, 1, 3), "bad CONNECT"
            host_len = _recvn(conn, 1)[0]
            _recvn(conn, host_len + 2)  # host + port, contents irrelevant
            conn.sendall(b"\x05\x00\x00\x01" + b"\x00" * 4 + b"\x00\x00")
            (qlen,) = struct.unpack(">H", _recvn(conn, 2))
            query = DNSRecord.parse(_recvn(conn, qlen))
            reply = query.reply()
            reply.add_answer(
                RR(query.q.qname, QTYPE.A, rdata=A("93.184.216.34"), ttl=60))
            packed = reply.pack()
            conn.sendall(struct.pack(">H", len(packed)) + packed)
        finally:
            conn.close()
            srv.close()


class TestTorUpstream(unittest.TestCase):
    def test_dormant_on_this_host(self):
        # MECHANISM: no tor binary on PATH (verified at build time),
        # so the module must report itself dormant.
        self.assertTrue(tor_upstream.DORMANT)

    def test_live_path_refuses_without_tor(self):
        # DOCTRINE: the refusal IS the feature — never fake the road.
        with self.assertRaises(tor_upstream.TorDormantError):
            tor_upstream.resolve("example.com")

    def test_handshake_against_mock_socks(self):
        # MECHANISM: the test-only _connect injection lets the real
        # handshake code run against the mock; production callers can
        # never pass it by accident (it has no default meaning there).
        fake = FakeSocks5()
        fake.start()
        self.assertTrue(fake.ready.wait(5), "mock did not start")
        answers = tor_upstream.resolve(
            "example.com",
            _connect=lambda addr: socket.create_connection(
                ("127.0.0.1", fake.port), timeout=5),
        )
        self.assertEqual(answers, ["93.184.216.34"])
        fake.join(5)


if __name__ == "__main__":
    unittest.main()


# 93. Live, Love, and let Love, Live.
# All Rights Reserved, Without Prejudice. — Johnathan 'Qasparr' (Κασπάρρ) Monroe
