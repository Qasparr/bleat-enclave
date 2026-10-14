# BLEAT ENCLAVE · enclave/dns_server.py — the localhost registrar.
# Authority begins at home: this machine answers for its own names.
#
# "In the beginning was the Word, and the Word was with God,
#  and the Word was God." — John 1:1
#
# Hypothesis: a name need not be rented from a registrar to resolve.
#   On this machine, the enclave is its own authority.
# Method: an authoritative-only DNS server on 127.0.0.1:5353, backed by
#   a file registry; dnslib speaks the wire protocol, the registry
#   decides the answers.
# Observation: recorded in tests/test_dns.py — the server answers live.
# Result: names registered here resolve here. Nothing leaves the wire.
#
# dies Mercurii, 2026-10-14, Anno V:xii e.n. — 93.
#
# Penned by the scribe, Heru-Ra-Ha, for Johnathan 'Qasparr' (Κασπάρρ) Monroe,
# Keeper of the Secret Treasure.

"""The localhost registrar.

MECHANISM: ZoneRegistry is the book of names — a dict persisted as JSON,
  fail-closed on bad input (bad names and bad targets raise ValueError,
  never silently stored). EnclaveResolver answers DNS questions strictly
  from that book: known name + A query -> A record; anything else ->
  NXDOMAIN. The server is authoritative-only: it never recurses, never
  forwards, never asks the public internet. Unprivileged port 5353, bound
  to loopback only, so no privilege and no exposure.

DOCTRINE: your names, your rules. A name registered here is a fact on
  this wire, needing no one's permission and no one's rent.
"""

import ipaddress
import json
import os
import re
import tempfile

# MECHANISM: dnslib is the wire-protocol engine (query parse, response
# pack). It lives in the project venv (.venv); the import is lazy-guarded
# so the registry stays usable even where dnslib is absent, while the
# server itself refuses to start without it — fail-closed, never half-up.
try:
    from dnslib import DNSRecord, QTYPE, RCODE, RR, A
    from dnslib.server import BaseResolver, DNSServer

    _DNSLIB = True
except ImportError:  # pragma: no cover - exercised only without the venv
    _DNSLIB = False

# DOCTRINE: loopback only, unprivileged port. The enclave does not bind
# a public face and does not need root. Sovereignty without privilege.
LISTEN_ADDRESS = "127.0.0.1"
LISTEN_PORT = 5353

DEFAULT_REGISTRY_PATH = os.path.expanduser("~/.bleat-enclave/registry.json")

# MECHANISM: names are hostnames by the old rules — labels of letters,
# digits, hyphens; dots between labels; case-insensitive. Single labels
# ("bleat") are allowed: this is a local book, not the public root.
_NAME_RE = re.compile(
    r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$",
    re.IGNORECASE,
)


class ZoneRegistry:
    """The book of names.

    MECHANISM: an in-memory dict, canonicalized (lowercase, no trailing
      dot), persisted as JSON. Every mutation validates first and saves
      atomically (tmp file + rename), so a crash never leaves half a book.
    """

    def __init__(self, path=DEFAULT_REGISTRY_PATH):
        # DOCTRINE: the path is injectable so tests use a tmp book and
        # never touch the operator's real registry.
        self.path = path
        self._names = {}
        self.load()

    @staticmethod
    def _canon(name):
        # MECHANISM: DNS is case-insensitive and the trailing dot is
        # decoration; both are normalized so "BLEAT." and "bleat" are
        # the same fact.
        return name.rstrip(".").lower()

    @staticmethod
    def _check_name(name):
        if not isinstance(name, str) or not _NAME_RE.match(name.rstrip(".")):
            raise ValueError("bad name: %r — letters, digits, hyphens, dots" % (name,))

    @staticmethod
    def _check_target(target):
        # DOCTRINE: v0.1 serves A records (IPv4) only. An unparsable or
        # non-IPv4 target is refused loudly, never stored as a hope.
        try:
            ip = ipaddress.ip_address(target)
        except ValueError:
            raise ValueError("bad target: %r — not an IP address" % (target,))
        if ip.version != 4:
            raise ValueError("bad target: %r — v0.1 serves IPv4 (A) only" % (target,))

    def register(self, name, target):
        """Write a name -> address fact into the book."""
        self._check_name(name)
        self._check_target(target)
        self._names[self._canon(name)] = str(ipaddress.ip_address(target))
        self.save()
        return self._canon(name)

    def resolve(self, name):
        """Read a fact from the book; None if the name is unknown."""
        return self._names.get(self._canon(name))

    def names(self):
        """Every registered name, sorted — the enclave's own root list."""
        return sorted(self._names)

    def load(self):
        # MECHANISM: a missing file is an empty book, not an error —
        # the registrar starts clean on first run.
        if not os.path.exists(self.path):
            self._names = {}
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._names = {self._canon(k): v for k, v in data.get("names", {}).items()}

    def save(self):
        # MECHANISM: atomic write — tmp file in the same directory, then
        # rename. A crash mid-save leaves the old book intact.
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"names": self._names}, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


class EnclaveResolver(BaseResolver):
    """Answers DNS questions strictly from the book.

    MECHANISM: dnslib calls resolve() per query. We look up the
      canonical name; a hit on an A/ANY question becomes one A answer
      with a 60-second TTL. Anything else — unknown name, wrong type —
      is NXDOMAIN. No recursion, no forwarding, no upstream: the buck
      stops at the registry.
    """

    def __init__(self, registry):
        self.registry = registry

    def resolve(self, request, handler):
        if not _DNSLIB:  # pragma: no cover
            raise RuntimeError("dnslib is required to serve DNS")
        # MECHANISM: the file is the truth — reload it on every query
        # so a `bleat register` at the counter is instantly visible on
        # the wire, even from a separate process. The zone is tiny;
        # the cost is nothing and the guarantee is everything.
        self.registry.load()
        qname = str(request.q.qname).rstrip(".").lower()
        reply = request.reply()
        target = self.registry.resolve(qname)
        if target and request.q.qtype in (QTYPE.A, QTYPE.ANY):
            # DOCTRINE: the enclave answers what it knows and says
            # "no such name" for the rest. NXDOMAIN is honesty, not refusal.
            reply.add_answer(RR(qname, QTYPE.A, rdata=A(target), ttl=60))
        else:
            reply.header.rcode = RCODE.NXDOMAIN
        return reply


class ServerGroup:
    """The UDP and TCP listeners as one unit.

    MECHANISM: both listeners share the resolver; stop() brings both
      down. The `transports` property reports which transports actually
      bound — honest about the machine it's on.
    """

    def __init__(self, servers):
        # servers: list of (transport_name, DNSServer)
        self._servers = servers

    @property
    def transports(self):
        """Transport names that bound, e.g. ['udp', 'tcp']."""
        return [name for name, _ in self._servers]

    def stop(self):
        # MECHANISM: dnslib's stop() only halts the serve loop — the
        # listening socket stays bound behind it. server_close() frees
        # the port, so a later server (or the next test) can bind it.
        # Without this, sequential tests die with EADDRINUSE.
        for _, server in self._servers:
            try:
                server.stop()
            finally:
                server.server.server_close()


def start_background(registry=None, address=LISTEN_ADDRESS, port=LISTEN_PORT):
    """Start the server on daemon threads; returns a ServerGroup.

    MECHANISM: binds UDP *and* TCP on the loopback port, the way real
      nameservers do (RFC 7766). Where the machine forbids UDP traffic
      — this sandbox answers sendto with Operation not permitted — the
      failure is noted and TCP carries the enclave. The server never
      dies for want of one transport.
    """
    if not _DNSLIB:
        raise RuntimeError(
            "dnslib is not installed — create the venv per the README "
            "(.venv/bin/pip install dnslib) and run with .venv/bin/python"
        )
    registry = registry or ZoneRegistry()
    servers = []
    try:
        udp = DNSServer(EnclaveResolver(registry), port=port,
                        address=address, tcp=False)
        udp.start_thread()
        servers.append(("udp", udp))
    except OSError as exc:
        # DOCTRINE: say what happened, keep serving. A transport the
        # machine forbids is a fact about the machine, not a failure
        # of the design.
        print("note: UDP unavailable (%s) — TCP carries the enclave" % exc)
    tcp = DNSServer(EnclaveResolver(registry), port=port,
                    address=address, tcp=True)
    tcp.start_thread()
    servers.append(("tcp", tcp))
    print("bleat-enclave DNS on %s:%d via %s — %d name(s) registered"
          % (address, port, "+".join(t for t, _ in servers),
             len(registry.names())))
    return ServerGroup(servers)


def serve(registry=None, address=LISTEN_ADDRESS, port=LISTEN_PORT):
    """Serve forever in the foreground (the `serve` entry point)."""
    import threading

    group = start_background(registry=registry, address=address, port=port)
    try:
        # MECHANISM: both listeners already run on daemon threads;
        # the foreground simply waits, so Ctrl-C unwinds cleanly.
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        group.stop()


# 93. Live, Love, and let Love, Live.
# All Rights Reserved, Without Prejudice. — Johnathan 'Qasparr' (Κασπάρρ) Monroe
