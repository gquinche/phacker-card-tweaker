"""Standalone SVG card-front rendering and packaging.

This module keeps the card SVG export separate from the HTML/PDF renderer. The
export is intentionally explicit: every SVG contains a paper infill and a
visible outer border, while the chart state is carried as a boolean
``difference`` value instead of leaking the older ``significant`` name into the
new export format.
"""

from __future__ import annotations

import json
import re
import zipfile
from collections.abc import Iterable, Sequence
from html import escape

from . import chart_generators as cg
from .dice_render import chart_label
from .ink_control import preview_hex
from .paper import paper_stock
from .pseudo_stats import footer_text

CARD_SVG_SIZES = {
    "print": {
        "view_width": 412.7,
        "view_height": 577.9,
        "width_attr": "41.27mm",
        "height_attr": "57.79mm",
    },
    "hand": {
        "view_width": 234.0,
        "view_height": 327.0,
        "width_attr": "234px",
        "height_attr": "327px",
    },
    "verdict": {
        "view_width": 140.0,
        "view_height": 190.0,
        "width_attr": "140px",
        "height_attr": "190px",
    },
}

_CARD_SVG_RE = re.compile(
    r'<svg\b[^>]*\bviewBox="([^"]+)"[^>]*>(.*)</svg>\s*$',
    re.DOTALL,
)
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def difference_label(difference: bool) -> str:
    """Return the player-facing label for the boolean graph state."""
    return "DIFFERENCE" if difference else "NO DIFFERENCE"


def _safe_hex(value: object, fallback: str) -> str:
    text = str(value)
    return text.lower() if _HEX_RE.fullmatch(text) else fallback


def _finding_ink(cfg: dict, difference: bool) -> str:
    """Resolve the configured finding ink, with a small test-friendly fallback."""
    page = "effect" if difference else "no_effect"
    if isinstance(cfg.get("cmyk"), dict) and page in cfg["cmyk"]:
        return _safe_hex(preview_hex(cfg, page), "#2b2b2b")
    palette_key = "SIG" if difference else "NULL"
    return _safe_hex(cfg.get("palette", {}).get(palette_key), "#2b2b2b")


def _size_info(size: str) -> dict[str, float | str]:
    try:
        return CARD_SVG_SIZES[size]
    except KeyError as exc:
        choices = ", ".join(CARD_SVG_SIZES)
        raise ValueError(f"Unsupported card SVG size {size!r}; choose {choices}") from exc


def _embedded_chart(svg_text: str, *, x: float, y: float, width: float, height: float) -> str:
    match = _CARD_SVG_RE.search(svg_text)
    if match is None:
        raise ValueError("Rendered chart did not contain a usable SVG root")
    view_box, body = match.groups()
    return (
        f'<svg x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        f'viewBox="{escape(view_box, quote=True)}" preserveAspectRatio="xMidYMid meet" '
        f'aria-hidden="true">{body}</svg>'
    )


def _card_id(chart: str, difference: bool) -> str:
    return f"{'D' if difference else 'N'}-{chart}"


def card_specs(
    charts: Iterable[str],
    seed: int,
    differences: Iterable[bool],
) -> list[dict[str, object]]:
    """Build validated export specs with a boolean ``difference`` field."""
    selected_charts = [chart for chart in charts if chart in cg.GENERATOR_NAMES]
    selected_states: list[bool] = []
    for difference in differences:
        if not isinstance(difference, bool):
            raise TypeError("card SVG difference states must be booleans")
        if difference not in selected_states:
            selected_states.append(difference)

    return [
        {"chart": chart, "difference": difference, "seed": int(seed)}
        for chart in selected_charts
        for difference in selected_states
    ]


def render_card_svg(
    chart: str,
    difference: bool,
    seed: int,
    cfg: dict,
    *,
    size: str = "print",
    card_id: str | None = None,
) -> str:
    """Render one self-contained full card-front SVG.

    ``difference`` is intentionally a strict boolean at this boundary. Internally
    it maps to the existing chart generator's significant/no-effect switch, but
    exported SVG metadata and the ZIP manifest use the clearer ``difference``
    field requested by the Card SVG page.
    """
    if chart not in cg.GENERATOR_NAMES:
        raise ValueError(f"Unknown chart type: {chart}")
    if not isinstance(difference, bool):
        raise TypeError("difference must be a boolean")

    info = _size_info(size)
    view_width = float(info["view_width"])
    view_height = float(info["view_height"])
    card_cfg = cfg.get("card", {})
    print_cfg = cfg.get("print", {})
    paper = paper_stock(card_cfg.get("paper", "white"))
    paper_hex = _safe_hex(paper["hex"], "#ffffff")
    edge_hex = _safe_hex(paper["edge"], "#d9d9d9")
    ink_hex = _finding_ink(cfg, difference)
    identity = card_id or _card_id(chart, difference)
    label = difference_label(difference)

    border_width = max(1.5, min(view_width, view_height) * 0.008)
    inset = max(10.0, view_width * 0.07)
    band_pct = max(0.0, min(100.0, float(cfg.get("band_pct", 20.0))))
    band_height = view_height * band_pct / 100.0
    footer_height = max(22.0, view_height * 0.075) if card_cfg.get("show_footer", False) else 0.0
    chart_x = inset
    chart_y = band_height + max(8.0, inset * 0.65)
    chart_width = max(1.0, view_width - inset * 2)
    chart_height = max(1.0, view_height - chart_y - footer_height - inset * 0.7)

    if size == "print":
        if print_cfg.get("round_corners", False):
            corner_radius = max(0.0, float(print_cfg.get("corner_radius_mm", 3.0))) * 10.0
        else:
            corner_radius = 0.0
    else:
        corner_radius = min(12.0, view_width * 0.05)

    chart_svg = cg.render_svg_bare(chart, difference, int(seed), cfg, ink_hex)
    chart_markup = _embedded_chart(
        chart_svg,
        x=chart_x,
        y=chart_y,
        width=chart_width,
        height=chart_height,
    )

    chart_opacity = max(0.0, min(1.0, float(card_cfg.get("chart_opacity", 0.6))))
    stamp_markup = ""
    if card_cfg.get("show_stamp", True):
        stamp_width = max(20.0, view_width * 0.105)
        stamp_height = max(12.0, view_height * 0.04)
        stamp_x = view_width - stamp_width - inset * 0.35
        stamp_y = view_height - footer_height - stamp_height - inset * 0.35
        stamp_markup = (
            f'<rect x="{stamp_x:.2f}" y="{stamp_y:.2f}" width="{stamp_width:.2f}" '
            f'height="{stamp_height:.2f}" rx="2" fill="none" stroke="#000000" '
            f'stroke-opacity="0.20" stroke-width="{max(1.0, border_width * 0.55):.2f}" '
            'transform="rotate(-8)" aria-hidden="true"/>'
        )

    crease_markup = ""
    if card_cfg.get("show_creases", True):
        crease_markup = (
            f'<path d="M {view_width / 2:.2f} 0 V {view_height:.2f}" stroke="#000000" '
            f'stroke-opacity="0.08" stroke-width="1" aria-hidden="true"/>'
            f'<path d="M 0 {view_height / 2:.2f} H {view_width:.2f}" stroke="#000000" '
            f'stroke-opacity="0.12" stroke-width="1" aria-hidden="true"/>'
        )

    footer_markup = ""
    if footer_height:
        footer_y = view_height - footer_height
        footer_markup = (
            f'<rect x="0" y="{footer_y:.2f}" width="{view_width:.2f}" height="{footer_height:.2f}" '
            f'fill="{paper_hex}" stroke="none"/>'
            f'<path d="M {inset:.2f} {footer_y + 1:.2f} H {view_width - inset:.2f}" '
            'stroke="#000000" stroke-opacity="0.20" stroke-width="1"/>'
            f'<text x="{inset:.2f}" y="{footer_y + footer_height * 0.62:.2f}" '
            'font-family="Courier New, monospace" font-size="12" letter-spacing="1.2" '
            'fill="#222222">'
            f'{escape(footer_text(identity, difference))}</text>'
        )

    show_id = bool(print_cfg.get("show_card_id", True)) if size == "print" else False
    id_markup = (
        f'<text x="{view_width - inset * 0.35:.2f}" y="{view_height - 3:.2f}" '
        'text-anchor="end" font-family="Courier New, monospace" font-size="7" '
        'fill="#000000" fill-opacity="0.22">'
        f'{escape(identity)}</text>'
        if show_id
        else ""
    )

    metadata = json.dumps(
        {"chart": chart, "difference": difference, "seed": int(seed), "card_id": identity},
        separators=(",", ":"),
    )
    title = escape(f"{label} card — {chart_label(chart)}")
    outer_x = border_width / 2
    outer_y = border_width / 2
    outer_width = view_width - border_width
    outer_height = view_height - border_width

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{info["width_attr"]}" height="{info["height_attr"]}" viewBox="0 0 {view_width:g} {view_height:g}" role="img" aria-label="{title}" data-difference="{str(difference).lower()}">
  <title>{title}</title>
  <metadata>{metadata}</metadata>
  <rect id="card-infill" x="{outer_x:.2f}" y="{outer_y:.2f}" width="{outer_width:.2f}" height="{outer_height:.2f}" rx="{corner_radius:.2f}" fill="{paper_hex}"/>
  {crease_markup}
  <rect id="difference-band" x="0" y="0" width="{view_width:.2f}" height="{band_height:.2f}" fill="{ink_hex}"/>
  <text x="{view_width / 2:.2f}" y="{band_height * 0.60:.2f}" text-anchor="middle" font-family="Georgia, serif" font-size="{max(11.0, view_width * 0.052):.2f}" font-weight="700" letter-spacing="3" fill="{paper_hex}">{label}</text>
  <g id="card-graphic" opacity="{chart_opacity:.3f}">{chart_markup}</g>
  {footer_markup}
  {stamp_markup}
  {id_markup}
  <rect id="card-border" x="{outer_x:.2f}" y="{outer_y:.2f}" width="{outer_width:.2f}" height="{outer_height:.2f}" rx="{corner_radius:.2f}" fill="none" stroke="{edge_hex}" stroke-width="{border_width:.2f}"/>
</svg>'''


def card_filename(index: int, spec: dict[str, object]) -> str:
    chart = str(spec["chart"]).replace("_", "-")
    state = "difference" if bool(spec["difference"]) else "no-difference"
    return f"card-{index:02d}-{chart}-{state}.svg"


def render_preview_html(specs: Sequence[dict[str, object]], svgs: Sequence[str]) -> str:
    """Wrap card SVGs into a compact Streamlit iframe gallery."""
    cards = []
    for index, (spec, svg) in enumerate(zip(specs, svgs), start=1):
        chart = escape(chart_label(str(spec["chart"])))
        state = escape(difference_label(bool(spec["difference"])))
        cards.append(
            f'<figure><div class="card-svg">{svg}</div><figcaption>'
            f'<strong>{index:02d}</strong><span>{chart}</span><small>{state} · difference={str(bool(spec["difference"])).lower()}</small>'
            "</figcaption></figure>"
        )
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 18px; background: #2f2a24; color: #f6f1e7; font-family: Inter, Arial, sans-serif; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 18px; align-items: start; }}
figure {{ margin: 0; min-width: 0; }}
.card-svg {{ width: 100%; }}
.card-svg > svg {{ display: block; width: 100%; height: auto; filter: drop-shadow(0 5px 8px rgba(0,0,0,.28)); }}
figcaption {{ display: grid; grid-template-columns: auto 1fr; gap: 2px 8px; padding: 8px 4px 0; align-items: baseline; }}
strong {{ font-size: 10px; letter-spacing: .12em; }}
span {{ font-size: 13px; }}
small {{ grid-column: 2; color: #d1c8b9; font-size: 11px; }}
</style></head><body><main class="grid">{''.join(cards)}</main></body></html>'''


def build_cards_zip(
    specs: Sequence[dict[str, object]],
    svgs: Sequence[str],
    *,
    size: str,
) -> bytes:
    """Package standalone card SVGs and a manifest with boolean differences."""
    _size_info(size)
    if len(specs) != len(svgs):
        raise ValueError("card SVG specs and rendered SVGs must have the same length")
    manifest = {
        "schema_version": 1,
        "size": size,
        "border": True,
        "infill": True,
        "difference_field": "difference",
        "cards": [
            {
                "filename": card_filename(index, spec),
                "chart": spec["chart"],
                "difference": bool(spec["difference"]),
                "seed": int(spec["seed"]),
            }
            for index, spec in enumerate(specs, start=1)
        ],
    }
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, (spec, svg) in enumerate(zip(specs, svgs), start=1):
            archive.writestr(card_filename(index, spec), svg)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    return buffer.getvalue()
