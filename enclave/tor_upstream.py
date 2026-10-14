# BLEAT ENCLAVE · enclave/tor_upstream.py — the hidden road out.
# DORMANT: written, tested against a mock, never faked live.
#
# "You will know the truth, and the truth will set you free." — John 8:32
#
# Hypothesis: when the enclave must ask the public internet a question,
#   it should ask through Tor — no direct wire, no leaking origin.
# Method: DNS-over-TCP (RFC 7766) carried inside a SOCKS5 CONNECT
#   (RFC 1928) to a Tor SOCKS port. The handshake bytes are real;
#   the refusal to run them without Tor is realer.
# Observation: evaluated at import — shutil.which("tor") decides.
#   On this host, 2026-10-14: no tor binary. DORMANT.
# Result: the module exists, the code path is tested against a mock
#   SOCKS5 speaker, and the live path raises instead of pretending.
#
# dies Mercurii, 2026-10-14, Anno V:xii e.n. — 93.
#
# Penned by the scribe, Heru-Ra-Ha, for Johnathan 'Qasparr' (Κασπάρρ) Monroe,
# Keeper of the Secret Treasure.

"""Upstream resolution via Tor SOCKS5 — DORMANT on this host.

MECHANISM: DORMANT is evaluated live at import time: if no `tor` binary
  is on PATH, the module refuses every live call with TorDormantError.
  The SOCKS5 handshake and DNS-over-TCP framing below are genuine
  implementations (RFC 1928 + RFC 7766), exercised by tests against a
  mock SOCKS5 speaker — so the code is proven without ever claiming a
  Tor circuit that does not exist.

DOCTRINE: honesty over completeness. A dormant module that says so is
  worth more than a live-looking one that fakes it. When Tor is
  installed on the operator's machine, DORMANT flips itself and the
  same code runs for real — no rewrite, just truth catching up.
"""

import shutil
import socket
import struct

try:
    from dnslib import DNSRecord, QTYPE

    _DNSLIB = True
except ImportError:  # pragma: no cover
    _DNSLIB = False

# MECHANISM: evaluated at import, on the machine that imports it. This
# is the whole honesty mechanism — no flag to forget, no config to lie.
DORMANT = shutil.which("tor") is None

DEFAULT_SOCKS_HOST = "127.0.0.1"
DEFAULT_SOCKS_PORT = 9050
DEFAULT_DNS_HOST = "1.1.1.1"  # the public resolver asked *through* Tor


class TorDormantError(RuntimeError):
    """Raised when the live Tor path is asked for without Tor present."""


class TorProtocolError(RuntimeError):
    """Raised when the SOCKS5 or DNS framing misbehaves."""


def _recvn(sock, n):
    # MECHANISM: TCP is a stream, not messages — read exactly n bytes
    # or fail loudly. Short reads are protocol errors, not patience tests.
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise TorProtocolError("connection closed mid-handshake")
        buf += chunk
    return buf


def _socks5_connect(connect, socks_host, socks_port, dns_host, dns_port=53):
    """Open a TCP tunnel to dns_host:53 through a SOCKS5 proxy.

    MECHANISM: RFC 1928, no-authentication method. Greeting ->
      method selection -> CONNECT request (domain-name address type) ->
      proxy's reply. Returns the tunnelled socket, ready for
      DNS-over-TCP bytes.
    """
    sock = connect((socks_host, socks_port))
    try:
        sock.sendall(b"\x05\x01\x00")  # VER=5, 1 method, NO AUTH
        ver, method = _recvn(sock, 2)
        if (ver, method) != (5, 0):
            raise TorProtocolError(
                "SOCKS5 method rejected: ver=%d method=%d" % (ver, method)
            )
        host_b = dns_host.encode("ascii")
        if len(host_b) > 255:
            raise TorProtocolError("DNS host name too long for SOCKS5")
        req = (
            b"\x05\x01\x00\x03"  # VER, CONNECT, RSV, ATYP=domain
            + bytes([len(host_b)])
            + host_b
            + struct.pack(">H", dns_port)
        )
        sock.sendall(req)
        ver, rep, _, atyp = _recvn(sock, 4)
        if ver != 5 or rep != 0:
            raise TorProtocolError("SOCKS5 CONNECT failed: rep=%d" % rep)
        # Consume the bound address per ATYP so the stream is positioned
        # exactly at the start of our DNS bytes.
        if atyp == 1:  # IPv4
            _recvn(sock, 4 + 2)
        elif atyp == 3:  # domain
            _recvn(sock, _recvn(sock, 1)[0] + 2)
        elif atyp == 4:  # IPv6
            _recvn(sock, 16 + 2)
        else:
            raise TorProtocolError("SOCKS5 unknown ATYP=%d" % atyp)
        return sock
    except BaseException:
        sock.close()
        raise


def _dns_over_tcp(sock, qname):
    """Send one DNS question over an established TCP tunnel; return answers.

    MECHANISM: RFC 7766 framing — 2-byte big-endian length prefix, then
      the query. dnslib packs the question and parses the reply.
    """
    if not _DNSLIB:
        raise RuntimeError("dnslib is required for Tor upstream queries")
    query = DNSRecord.question(qname).pack()
    sock.sendall(struct.pack(">H", len(query)) + query)
    (length,) = struct.unpack(">H", _recvn(sock, 2))
    reply = DNSRecord.parse(_recvn(sock, length))
    return [str(rr.rdata) for rr in reply.rr if rr.rtype == QTYPE.A]


def resolve(name, dns_host=DEFAULT_DNS_HOST,
            socks_host=DEFAULT_SOCKS_HOST, socks_port=DEFAULT_SOCKS_PORT,
            _connect=None):
    """Resolve a public name through Tor. Refuses unless Tor exists.

    MECHANISM: the live path (no _connect given) is gated on DORMANT —
      without a tor binary this raises TorDormantError, always. The
      _connect parameter exists for tests only: it injects a socket
      factory so the real handshake code runs against a mock SOCKS5
      speaker. Passing it in production would be lying to yourself;
      don't.
    """
    if DORMANT and _connect is None:
        raise TorDormantError(
            "Tor upstream is DORMANT on this host: no `tor` binary found. "
            "Install Tor and this same code runs for real — nothing faked."
        )
    connect = _connect or socket.create_connection
    sock = _socks5_connect(connect, socks_host, socks_port, dns_host)
    try:
        return _dns_over_tcp(sock, name)
    finally:
        sock.close()


# 93. Live, Love, and let Love, Live.
# All Rights Reserved, Without Prejudice. — Johnathan 'Qasparr' (Κασπάρρ) Monroe
