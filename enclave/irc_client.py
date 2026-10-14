# BLEAT ENCLAVE · enclave/irc_client.py — blestirc, the enclave relay.
# A minimal IRC client: connect, join, speak, listen. Localhost by default.
#
# "As iron sharpens iron, so one person sharpens another." — Proverbs 27:17
#
# Hypothesis: the enclave needs a mouth as well as a memory — somewhere
#   its people can gather and be heard, on a wire it controls.
# Method: plain RFC 1459/2812 client chatter over TCP — NICK, USER, JOIN,
#   PRIVMSG, PING/PONG — parsed line by line, no more, no less.
# Observation: recorded in tests/test_irc.py against a local test double.
# Result: connect -> join -> send -> receive, all working, all legible.
#
# dies Mercurii, 2026-10-14, Anno V:xii e.n. — 93.
#
# Penned by the scribe, Heru-Ra-Ha, for Johnathan 'Qasparr' (Κασπάρρ) Monroe,
# Keeper of the Secret Treasure.

"""blestirc — a minimal, honest IRC client.

MECHANISM: a TCP socket plus a line reader. connect() performs the
  NICK/USER handshake and waits for the 001 welcome; join() sends JOIN
  and waits for the echo; send_message() emits PRIVMSG; recv_message()
  returns parsed dicts and answers PING with PONG by itself, because a
  client that won't pong is a client that gets dropped. Everything is
  blocking with explicit timeouts — fail-closed, never hanging forever.

DOCTRINE: localhost by default. The enclave's relay is assumed to be
  its own until the operator says otherwise — server and port are
  constructor arguments, not hidden constants.
"""

import socket
import time

DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 6667


class IRCError(RuntimeError):
    """The relay refused us, or the wire went quiet."""


def parse_line(line):
    """Split a raw IRC line into prefix / command / params.

    MECHANISM: [:prefix] COMMAND [params...] [:trailing]. The trailing
      parameter (after " :") may contain spaces; everything before it
      splits on whitespace. Returns a dict; never raises on garbage —
      unparseable input yields command=None.
    """
    line = line.rstrip("\r\n")
    prefix = None
    if line.startswith(":"):
        prefix, _, line = line[1:].partition(" ")
    if " :" in line:
        head, _, trailing = line.partition(" :")
        params = head.split()
        params.append(trailing)
    else:
        params = line.split()
    command = params.pop(0).upper() if params else None
    return {"prefix": prefix, "command": command, "params": params,
            "raw": line}


class IRCClient:
    """A small synchronous IRC client.

    MECHANISM: one socket, one file reader. All waiting loops carry a
      deadline (time.monotonic), so a silent server produces IRCError,
      not an eternal block.
    """

    def __init__(self, server=DEFAULT_SERVER, port=DEFAULT_PORT,
                 nick="blestirc", username="blestirc",
                 realname="blestirc - enclave relay"):
        # DOCTRINE: the defaults describe the enclave's posture — talk
        # to yourself first; the world is opt-in.
        self.server = server
        self.port = port
        self.nick = nick
        self.username = username
        self.realname = realname
        self._sock = None
        self._reader = None

    # -- wire primitives -------------------------------------------------
    def _send(self, line):
        # MECHANISM: IRC frames are Latin-1-ish bytes ending in CRLF;
        # utf-8 with replacement keeps the client's tongue while never
        # crashing on a odd byte from the wire.
        self._sock.sendall(line.encode("utf-8", "replace") + b"\r\n")

    def _recv_line(self, timeout):
        self._sock.settimeout(timeout)
        try:
            line = self._reader.readline()
        except socket.timeout:
            return None
        if line == "":
            raise IRCError("server closed the connection")
        return line

    def _wait_for(self, predicate, timeout, what):
        # MECHANISM: the shared waiting room — every handshake step
        # funnels through here, PINGs answered on the way past.
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise IRCError("timed out waiting for %s" % what)
            parsed = self._next_parsed(remaining)
            if parsed is None:
                continue
            if predicate(parsed):
                return parsed

    def _next_parsed(self, timeout):
        # MECHANISM: one line in, PING answered, anything else parsed
        # and returned. The pong is automatic because politeness is
        # protocol here — RFC 1459 4.6.2.
        line = self._recv_line(timeout)
        if line is None:
            return None
        parsed = parse_line(line)
        if parsed["command"] == "PING":
            token = parsed["params"][-1] if parsed["params"] else ""
            self._send("PONG :%s" % token)
            return None
        return parsed

    # -- the public verbs --------------------------------------------------
    def connect(self, timeout=15):
        """Open the wire and complete the NICK/USER handshake.

        MECHANISM: create_connection to server:port, introduce
          ourselves, then wait for numeric 001 (RPL_WELCOME) — the
          server's word that we exist. ERROR lines and timeouts raise.
        """
        self._sock = socket.create_connection(
            (self.server, self.port), timeout=timeout)
        self._reader = self._sock.makefile("r", encoding="utf-8",
                                           errors="replace")
        self._send("NICK %s" % self.nick)
        self._send("USER %s 0 * :%s" % (self.username, self.realname))

        def welcomed(p):
            if p["command"] == "ERROR":
                raise IRCError("server error: %s" % p["raw"])
            return p["command"] == "001"

        self._wait_for(welcomed, timeout, "the 001 welcome")
        return self

    def join(self, channel, timeout=15):
        """Enter a channel; wait for the server's JOIN echo.

        MECHANISM: a channel name without '#' is normalized, because
          the operator's intent is clear and pedantry helps no one.
        """
        if not channel.startswith("#"):
            channel = "#" + channel
        self._send("JOIN %s" % channel)

        def joined(p):
            if p["command"] in ("403", "475", "474", "473"):
                raise IRCError("could not join %s: %s" % (channel, p["raw"]))
            return p["command"] == "JOIN" and channel in p["params"]

        self._wait_for(joined, timeout, "JOIN echo for %s" % channel)
        return channel

    def send_message(self, target, text):
        """Speak to a channel or a nick."""
        self._send("PRIVMSG %s :%s" % (target, text))

    def recv_message(self, timeout=15):
        """Next parsed message, or None on a quiet wire. PINGs auto-pong."""
        return self._next_parsed(timeout)

    def quit(self, message="leaving the enclave"):
        """Say goodbye politely, then close."""
        try:
            self._send("QUIT :%s" % message)
        finally:
            self.close()

    def close(self):
        for handle in (self._reader, self._sock):
            try:
                if handle is not None:
                    handle.close()
            except OSError:
                pass
        self._reader = None
        self._sock = None


# 93. Live, Love, and let Love, Live.
# All Rights Reserved, Without Prejudice. — Johnathan 'Qasparr' (Κασπάρρ) Monroe
