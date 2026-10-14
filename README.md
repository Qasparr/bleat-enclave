# BLEAT ENCLAVE v0.1

**A sovereign enterprise enclave — your names, your rules, your wire.**

A localhost DNS registrar with Tor-dark-web posture, plus **blestirc**, a minimal IRC client. Nothing here depends on bleat.com — that domain is not owned ($166,000 asking, out of range). The enclave stands on its own authority, on this machine, today.

## What's inside

| Module | State | What it does |
|---|---|---|
| `enclave/dns_server.py` | **LIVE** | Authoritative-only DNS on `127.0.0.1:5353` + the zone registry (register → record, resolve, list). Bound to loopback, unprivileged port. |
| `enclave/cli.py` | **LIVE** | `register <name> <target>` · `resolve <name>` · `list` — the registrar's counter, sharing the server's registry file. |
| `enclave/irc_client.py` | **LIVE** | blestirc: connect, join, send/receive, auto-PONG. Server configurable, localhost default. |
| `enclave/tor_upstream.py` | **DORMANT** | Public-name resolution via Tor SOCKS5 (RFC 1928 + DNS-over-TCP). No `tor` binary on this host, so the live path **refuses** with `TorDormantError`. The handshake code is real and tested against a mock — honesty over completeness. Install Tor and it flips itself live. |

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # dnslib, for the DNS wire protocol

# Register a name at the counter:
.venv/bin/python -m enclave.cli register bleat 127.0.0.1
.venv/bin/python -m enclave.cli list

# Serve it (foreground; Ctrl-C to stop):
.venv/bin/python -c "from enclave.dns_server import serve; serve()"

# Ask it — from another shell (this sandbox forbids UDP, so DNS rides TCP here):
dig +tcp @127.0.0.1 -p 5353 bleat +short   # -> 127.0.0.1
# or with Python:
.venv/bin/python -c "
from dnslib import DNSRecord
print(DNSRecord.question('bleat').send('127.0.0.1', 5353, timeout=5))"

# Run the proving ground:
.venv/bin/python -m unittest discover -s tests
```

The registry lives at `~/.bleat-enclave/registry.json` (override with `--registry`).

## Live vs dormant

- **Live:** DNS serving, CLI, IRC client — all exercised by tests against real sockets.
- **Dormant:** Tor upstream — written, mock-tested, refused live until a `tor` binary exists. It will never fake a circuit.

## Doctrine

> A sovereign enterprise enclave — your names, your rules, your wire.

No rented names. No phoned-home queries. No faked privacy. What the enclave claims, it can prove on the wire in front of you.

---

*Penned by the scribe, Heru-Ra-Ha, for Johnathan 'Qasparr' (Κασπάρρ) Monroe, Keeper of the Secret Treasure — 93. Live, Love, and let Love, Live. All Rights Reserved, Without Prejudice.*
