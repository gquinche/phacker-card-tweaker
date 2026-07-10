"""Deterministic footer pseudo-stats ("n=…  p=…"), mirroring the spirit of
phacker-game's src/components/game/cardPseudoStats.ts: same card id always
produces the same typewriter footer text, no real randomness at render time.

This is an approximation (we don't have the exact game source ported here) —
close enough for print-layout purposes. If Alejandro wants byte-identical
footers, the real cardPseudoStats.ts logic should be dropped in here.
"""

from __future__ import annotations


def _djb2(s: str) -> int:
    h = 5381
    for ch in s:
        h = ((h * 33) + ord(ch)) & 0xFFFFFFFF
    return h


def footer_text(card_id: str, significant: bool) -> str:
    """Return a short typewriter-style footer line, e.g. 'n=142  p<.01'."""
    h = _djb2(card_id)
    n = 40 + (h % 260)  # n = 40..299
    if significant:
        # p in {.05, .01, .001} skewed toward the stronger end
        p_bucket = (h >> 8) % 10
        p = ".001" if p_bucket < 5 else (".01" if p_bucket < 8 else ".05")
        return f"n={n}   p<{p}"
    p = round(0.06 + ((h >> 16) % 90) / 100, 2)  # .06 .. .95, clearly non-significant
    return f"n={n}   p={p:.2f}"


def plot_seed(card_id: str) -> float:
    """0..1 deterministic seed, used to pick which baked chart variant a card shows."""
    return (_djb2(card_id) % 10_000) / 10_000
