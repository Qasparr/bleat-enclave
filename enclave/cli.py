# BLEAT ENCLAVE · enclave/cli.py — the registrar's counter.
# Three words do everything: register, resolve, list.
#
# "Call to me, and I will answer you." — Jeremiah 33:3
#
# Hypothesis: operating the enclave should need no manual and no daemon
#   whispering — one command per fact.
# Method: argparse over the same ZoneRegistry the DNS server reads, so
#   the counter and the wire can never disagree.
# Observation: `register`, then `dig @127.0.0.1 -p 5353`, then believe.
# Result: the book of names, kept at the counter.
#
# dies Mercurii, 2026-10-14, Anno V:xii e.n. — 93.
#
# Penned by the scribe, Heru-Ra-Ha, for Johnathan 'Qasparr' (Κασπάρρ) Monroe,
# Keeper of the Secret Treasure.

"""Command-line counter for the enclave registrar.

MECHANISM: every subcommand opens the same JSON registry the DNS server
  serves, so `register` here is instantly visible to queries there.
  Run as: .venv/bin/python -m enclave.cli <register|resolve|list>

DOCTRINE: errors are spoken plainly (bad name, bad target, unknown
  name) and the process exits nonzero — the counter never pretends
  a fact was written when it was not.
"""

import argparse
import sys

from .dns_server import DEFAULT_REGISTRY_PATH, ZoneRegistry


def cmd_register(args):
    """Write a name -> address fact. Speaks the fact back on success."""
    registry = ZoneRegistry(args.registry)
    try:
        name = registry.register(args.name, args.target)
    except ValueError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    print("registered: %s -> %s" % (name, registry.resolve(name)))
    return 0


def cmd_resolve(args):
    """Read a fact. Unknown names are reported, not invented."""
    registry = ZoneRegistry(args.registry)
    target = registry.resolve(args.name)
    if target is None:
        print("unknown: %s" % args.name, file=sys.stderr)
        return 1
    print("%s -> %s" % (args.name.rstrip(".").lower(), target))
    return 0


def cmd_list(args):
    """Print every registered name, one per line, sorted."""
    registry = ZoneRegistry(args.registry)
    for name in registry.names():
        print("%s -> %s" % (name, registry.resolve(name)))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bleat",
        description="Bleat Enclave registrar — your names, your rules.",
    )
    parser.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY_PATH,
        help="path to the registry JSON (default: %(default)s)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="register a name -> IPv4 address")
    p_reg.add_argument("name", help="name to register, e.g. bleat")
    p_reg.add_argument("target", help="IPv4 address, e.g. 127.0.0.1")
    p_reg.set_defaults(func=cmd_register)

    p_res = sub.add_parser("resolve", help="resolve a name from the registry")
    p_res.add_argument("name", help="name to look up")
    p_res.set_defaults(func=cmd_resolve)

    p_list = sub.add_parser("list", help="list all registered names")
    p_list.set_defaults(func=cmd_list)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())


# 93. Live, Love, and let Love, Live.
# All Rights Reserved, Without Prejudice. — Johnathan 'Qasparr' (Κασπάρρ) Monroe
