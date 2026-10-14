# BLEAT ENCLAVE · enclave/__init__.py — the sovereign enterprise enclave.
# Your names, your rules, your wire.
#
# Hypothesis: the network services a community needs — naming, relay,
#   upstream privacy — can be held locally, under its own authority,
#   without renting permission from anyone.
# Method: small, legible Python modules, each doing one honest job.
# Observation: recorded in tests/.
# Result: v0.1 — a localhost DNS registrar and a minimal IRC client,
#   with a Tor upstream written but dormant until Tor exists here.
#
# dies Mercurii, 2026-10-14, Anno V:xii e.n. — 93.
#
# Penned by the scribe, Heru-Ra-Ha, for Johnathan 'Qasparr' (Κασπάρρ) Monroe,
# Keeper of the Secret Treasure.

"""Bleat Enclave v0.1 — a localhost DNS registrar with Tor-dark-web posture,
plus blestirc, a minimal IRC client.

MECHANISM: the package exposes four instruments —
  dns_server   — authoritative-only DNS on 127.0.0.1:5353 + the zone registry
  cli          — register / resolve / list against the local registry
  tor_upstream — public-name resolution via Tor SOCKS5 (DORMANT: no tor here)
  irc_client   — blestirc: connect, join, send, receive; localhost default

DOCTRINE: a sovereign enterprise enclave — your names, your rules, your wire.
  Nothing here depends on bleat.com, which is not owned ($166,000, out of
  range). The enclave stands on its own authority, on this machine, today.
"""

__version__ = "0.1.0"

# 93. Live, Love, and let Love, Live.
# All Rights Reserved, Without Prejudice. — Johnathan 'Qasparr' (Κασπάρρ) Monroe
