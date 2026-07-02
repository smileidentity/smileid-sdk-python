"""Generator-owned layer: wire models and thin per-operation request builders.

Everything in this package mirrors the wire contract (spec §5, §6) verbatim and
is written so a future code generator (Speakeasy / OpenAPI Generator) can own it
without touching the hand-written ``client``, ``errors`` and ``helpers`` trees.
"""
