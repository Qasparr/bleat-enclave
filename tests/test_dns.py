# BLEAT ENCLAVE · tests/test_dns.py — the registrar, proven on the wire.
#
# Hypothesis: the server answers from the book, and only from the book.
# Method: start a real server on 127.0.0.1:5353 against a tmp registry,
#   ask it real DNS questions, check the answers and the refusals.
# Observation: below — every assertion is a packet that went out and
#   came back.
# Result: names registered here resolve here; unknown names get NXDOMAIN.
#
# dies Mercurii, 2026-10-14, Anno V:xii e.n. — 93.
#
# Penned by the scribe, Heru-Ra-Ha, for Johnathan 'Qasparr' (Κασπάρρ) Monroe,
# Keeper of the Secret Treasure.

"""Live-wire tests for the localhost registrar.

MECHANISM: setUp starts a genuine DNSServer on 127.0.0.1:5353 in a
  background thread, backed by a throwaway registry file. Queries go
  out as real DNS packets (dnslib) and the answers are asserted. The
  registry object is shared with the resolver, so a register() mid-test
  is instantly visible on the wire — that binding is part of what's
  proven.

DOCTRINE: tests touch a tmp book, never the operator's real registry.
"""

import os
import tempfile
import time
import unittest

from dnslib import DNSRecord, QTYPE, RCODE

from enclave.cli import main as cli_main
from enclave.dns_server import LISTEN_PORT, ZoneRegistry, start_background


class TestRegistrar(unittest.TestCase):
    def setUp(self):
        # MECHANISM: a fresh book per test — no leakage between cases.
        self.tmp = tempfile.TemporaryDirectory()
        self.regpath = os.path.join(self.tmp.name, "registry.json")
        self.registry = ZoneRegistry(path=self.regpath)
        self.registry.register("bleat", "127.0.0.1")
        self.registry.register("relay.enclave", "10.0.0.5")
        self.server = start_background(registry=self.registry)
        time.sleep(0.3)  # let the thread bind before the first packet

    def tearDown(self):
        self.server.stop()
        self.tmp.cleanup()

    def _query(self, name, qtype="A"):
        # MECHANISM: DNS-over-TCP (RFC 7766). This sandbox forbids UDP
        # traffic outright, so the live proof rides TCP; the server
        # still binds UDP wherever the machine allows it. Note dnslib's
        # send() returns raw bytes over TCP — parse them back.
        raw = DNSRecord.question(name, qtype).send(
            "127.0.0.1", LISTEN_PORT, tcp=True, timeout=5)
        return DNSRecord.parse(raw)

    def test_known_name_answers_a_record(self):
        reply = self._query("bleat")
        self.assertEqual(reply.header.rcode, RCODE.NOERROR)
        self.assertEqual([str(rr.rdata) for rr in reply.rr], ["127.0.0.1"])

    def test_case_and_dot_insensitive(self):
        reply = self._query("BLEAT.")
        self.assertEqual([str(rr.rdata) for rr in reply.rr], ["127.0.0.1"])

    def test_unknown_name_gets_nxdomain(self):
        # DOCTRINE: honesty on the wire — no answer invented.
        reply = self._query("nosuchname")
        self.assertEqual(reply.header.rcode, RCODE.NXDOMAIN)
        self.assertEqual(reply.rr, [])

    def test_register_resolve_list_roundtrip(self):
        # MECHANISM: register mid-test; the live server must see it
        # because resolver and test share the registry object.
        self.registry.register("newnode", "192.0.2.7")
        self.assertEqual(self.registry.resolve("newnode"), "192.0.2.7")
        reply = self._query("newnode")
        self.assertEqual(reply.header.rcode, RCODE.NOERROR)
        self.assertEqual([str(rr.rdata) for rr in reply.rr], ["192.0.2.7"])
        self.assertIn("newnode", self.registry.names())
        self.assertIn("bleat", self.registry.names())

    def test_bad_input_refused_loudly(self):
        # DOCTRINE: fail-closed — garbage never becomes a fact.
        with self.assertRaises(ValueError):
            self.registry.register("bad name!", "127.0.0.1")
        with self.assertRaises(ValueError):
            self.registry.register("ok", "999.1.1.1")
        with self.assertRaises(ValueError):
            self.registry.register("ok", "not-an-ip")

    def test_cli_roundtrip(self):
        # MECHANISM: the counter speaks to the same book the wire reads.
        self.assertEqual(
            cli_main(["--registry", self.regpath, "register",
                      "clinode", "127.0.0.2"]), 0)
        self.assertEqual(
            cli_main(["--registry", self.regpath, "resolve", "clinode"]), 0)
        self.assertEqual(
            cli_main(["--registry", self.regpath, "list"]), 0)
        self.assertEqual(
            cli_main(["--registry", self.regpath, "resolve", "ghost"]), 1)
        # And the CLI's fact is on the wire too:
        reply = self._query("clinode")
        self.assertEqual([str(rr.rdata) for rr in reply.rr], ["127.0.0.2"])


if __name__ == "__main__":
    unittest.main()


# 93. Live, Love, and let Love, Live.
# All Rights Reserved, Without Prejudice. — Johnathan 'Qasparr' (Κασπάρρ) Monroe
