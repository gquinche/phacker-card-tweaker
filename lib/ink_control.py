"""Per-page CMYK recipes, interactive picker data, and print-ink auditing."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .colors import cmyk_to_hex, hex_to_rgb01

CHANNELS = ("C", "M", "Y", "K")
PAGE_KEYS = ("effect", "no_effect", "back")
PAGE_LABELS = {
    "effect": "EFFECT",
    "no_effect": "NO EFFECT",
    "back": "CARD BACK",
}

_DEVICE_RE = re.compile(
    r"device-cmyk\(\s*([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s*\)",
    re.I,
)
_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])")
_RGBA_RE = re.compile(
    r"rgba?\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s*,\s*([\d.]+))?\s*\)",
    re.I,
)
_SECTION_RE = re.compile(
    r'<section class="tw-page" data-page="([^"]+)">(.*?)</section>',
    re.I | re.S,
)
_STYLE_RE = re.compile(r"<style>(.*?)</style>", re.I | re.S)
_NAMED_RE = re.compile(
    r":\s*(cyan|magenta|yellow|black|red|green|blue|gray|white)\b",
    re.I,
)
_NAMED_HEX = {
    "cyan": "#00ffff",
    "magenta": "#ff00ff",
    "yellow": "#ffff00",
    "black": "#000000",
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "gray": "#808080",
    "white": "#ffffff",
}


def _remove_screen_media(css: str) -> str:
    """Remove nested @media screen blocks before auditing print ink."""
    marker = re.compile(r"@media\s+screen\s*\{", re.I)
    output: list[str] = []
    cursor = 0
    while True:
        match = marker.search(css, cursor)
        if not match:
            output.append(css[cursor:])
            break
        output.append(css[cursor:match.start()])
        depth = 0
        index = match.end() - 1
        while index < len(css):
            if css[index] == "{":
                depth += 1
            elif css[index] == "}":
                depth -= 1
                if depth == 0:
                    index += 1
                    break
            index += 1
        cursor = index
    return "".join(output)


def recipe(cfg: dict, page: str) -> list[int]:
    return [int(value) for value in cfg["cmyk"][page]]


def device_cmyk(cfg: dict, page: str) -> str:
    c, m, y, k = recipe(cfg, page)
    return f"device-cmyk({c}% {m}% {y}% {k}%)"


def preview_hex(cfg: dict, page: str) -> str:
    return cmyk_to_hex(*recipe(cfg, page))


def allowed_channels(cfg: dict, page: str) -> set[str]:
    values = cfg["print"].get("ink_policy", {}).get(page, list(CHANNELS))
    return {channel for channel in values if channel in CHANNELS}


def channel_rows(cfg: dict) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for page in PAGE_KEYS:
        values = recipe(cfg, page)
        for channel, value in zip(CHANNELS, values):
            rows.append({
                "page": PAGE_LABELS[page],
                "channel": channel,
                "coverage": value,
                "allowed": channel in allowed_channels(cfg, page),
            })
    return rows


def rgb_hex_to_cmyk(value: str) -> tuple[float, float, float, float]:
    r, g, b = hex_to_rgb01(value)
    k = 1 - max(r, g, b)
    if k >= 0.999999:
        return 0.0, 0.0, 0.0, 100.0
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    return tuple(round(max(0.0, channel) * 100, 2) for channel in (c, m, y, k))


def _rgb_to_cmyk(r: float, g: float, b: float) -> tuple[float, float, float, float]:
    return rgb_hex_to_cmyk(f"#{round(r):02x}{round(g):02x}{round(b):02x}")


def css_from_hex(value: str, target: str, use_cmyk: bool = True) -> str:
    if target != "pdf" or not use_cmyk:
        return value
    c, m, y, k = rgb_hex_to_cmyk(value)
    return f"device-cmyk({c}% {m}% {y}% {k}%)"


@dataclass(frozen=True)
class InkWarning:
    page: str
    color: str
    channels: tuple[str, ...]
    message: str


def _scan_colors(text: str) -> list[tuple[str, tuple[float, float, float, float]]]:
    found: list[tuple[str, tuple[float, float, float, float]]] = []
    for match in _DEVICE_RE.finditer(text):
        found.append((match.group(0), tuple(float(value) for value in match.groups())))
    scrubbed = _DEVICE_RE.sub("", text)
    for value in _HEX_RE.findall(scrubbed):
        found.append((value, rgb_hex_to_cmyk(value)))
    for match in _RGBA_RE.finditer(scrubbed):
        alpha = float(match.group(4) or 1)
        if alpha <= 0.01:
            continue
        found.append((match.group(0), _rgb_to_cmyk(*map(float, match.groups()[:3]))))
    for match in _NAMED_RE.finditer(scrubbed):
        name = match.group(1).lower()
        found.append((name, rgb_hex_to_cmyk(_NAMED_HEX[name])))
    return found


def audit_print_html(html: str, cfg: dict, tolerance: float = 0.75) -> dict:
    """Warn when a rendered page uses a CMYK channel outside its policy."""
    warnings: list[InkWarning] = []
    observed: dict[str, dict[str, int]] = {
        page: {channel: 0 for channel in CHANNELS} for page in PAGE_KEYS
    }

    for page, section in _SECTION_RE.findall(html):
        if page not in PAGE_KEYS:
            continue
        allowed = allowed_channels(cfg, page)
        for color, values in _scan_colors(section):
            active = tuple(
                channel for channel, value in zip(CHANNELS, values) if value > tolerance
            )
            for channel in active:
                observed[page][channel] += 1
            forbidden = tuple(channel for channel in active if channel not in allowed)
            if forbidden:
                warnings.append(InkWarning(
                    page=page,
                    color=color,
                    channels=forbidden,
                    message=(
                        f"{PAGE_LABELS[page]} uses {color}, activating "
                        f"{', '.join(forbidden)} outside policy {sorted(allowed)}."
                    ),
                ))

    # Shared CSS applies to every page, so only channels allowed by every page
    # may appear there. Page-specific inks belong in section markup instead.
    global_allowed = set(CHANNELS)
    for page in PAGE_KEYS:
        global_allowed &= allowed_channels(cfg, page)
    for style in _STYLE_RE.findall(html):
        # Screen-only shadows/textures are intentionally not print ink.
        printable_style = _remove_screen_media(style)
        for color, values in _scan_colors(printable_style):
            active = tuple(
                channel for channel, value in zip(CHANNELS, values) if value > tolerance
            )
            forbidden = tuple(channel for channel in active if channel not in global_allowed)
            if forbidden:
                warnings.append(InkWarning(
                    page="global_css",
                    color=color,
                    channels=forbidden,
                    message=(
                        f"Shared print CSS uses {color}, activating "
                        f"{', '.join(forbidden)} outside all page policies."
                    ),
                ))

    # Deduplicate repeated literals while retaining deterministic order.
    unique: list[InkWarning] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for warning in warnings:
        signature = (warning.page, warning.color, warning.channels)
        if signature not in seen:
            unique.append(warning)
            seen.add(signature)

    return {
        "safe": not unique,
        "warnings": unique,
        "observed": observed,
    }
