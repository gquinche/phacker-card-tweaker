"""Color helpers shared across the app: CMYK <-> hex, luminance, etc."""

from __future__ import annotations


def cmyk_to_rgb01(c: int, m: int, y: int, k: int) -> tuple[float, float, float]:
    """CMYK (0-100 each) -> RGB in 0..1 range (naive additive conversion,
    matches what a litografía quoting CMYK ink coverage expects)."""
    C, M, Y, K = c / 100, m / 100, y / 100, k / 100
    r = (1 - C) * (1 - K)
    g = (1 - M) * (1 - K)
    b = (1 - Y) * (1 - K)
    return r, g, b


def rgb01_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(v * 255):02x}" for v in rgb)


def cmyk_to_hex(c: int, m: int, y: int, k: int) -> str:
    return rgb01_to_hex(cmyk_to_rgb01(c, m, y, k))


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hex_to_rgb01(h: str) -> tuple[float, float, float]:
    r, g, b = hex_to_rgb(h)
    return r / 255, g / 255, b / 255


def hex_to_rgba_css(h: str, alpha: float) -> str:
    r, g, b = hex_to_rgb(h)
    return f"rgba({r},{g},{b},{alpha})"
