"""Render the real simplified-UI card-back SVG options offline.

The motif files are copied verbatim from phacker-game's
`experiment/simplified-ui/public/patterns`. The game applies them as CSS masks;
for browser + WeasyPrint parity here, we recolor the SVG ink and embed it as a
repeating data-URI background at the same low contrast.
"""
from __future__ import annotations

import base64
from pathlib import Path

from .ink_control import css_from_hex, device_cmyk, preview_hex
from .paper import paper_stock

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "card_backs"

CARD_BACK_OPTIONS: dict[str, dict[str, str]] = {
    "tex-stripe": {"label": "Master's · Stripe", "tier": "masters"},
    "tex-chevron": {"label": "PhD · Chevron", "tier": "phd"},
    "tex-argyle": {"label": "PhD · Argyle", "tier": "phd"},
    "tex-hexlattice": {"label": "Postdoc · Hex lattice", "tier": "postdoc"},
    "tex-scallop": {"label": "Postdoc · Scallop", "tier": "postdoc"},
    "tex-contour": {"label": "Nobel · Contour", "tier": "nobel"},
    "tex-flow": {"label": "Nobel · Flow", "tier": "nobel"},
    "tex-guilloche": {"label": "Experimental · Guilloche", "tier": "experimental"},
}
DEFAULT_CARD_BACK = "tex-chevron"
ROMAN_NUMERALS = ("I", "II", "III", "IV", "V")
SEAL_RING_TEXT = "DEPARTMENT OF REPRODUCIBILITY · DEPARTMENT OF REPRODUCIBILITY ·"


def card_back_tokens() -> list[str]:
    return list(CARD_BACK_OPTIONS)


def card_back_label(token: str) -> str:
    return CARD_BACK_OPTIONS.get(token, CARD_BACK_OPTIONS[DEFAULT_CARD_BACK])["label"]


def _resolved_token(token: str) -> str:
    return token if token in CARD_BACK_OPTIONS else DEFAULT_CARD_BACK


def pattern_data_uri(token: str, ink: str = "#2b2b2b") -> str:
    """Return the selected real SVG as a self-contained, recolored data URI."""
    resolved = _resolved_token(token)
    svg = (ASSET_DIR / f"{resolved}.svg").read_text(encoding="utf-8")
    # Hero Patterns ship as #000 fills. Guilloche is currentColor stroke-based.
    svg = svg.replace("#000000", ink).replace("#000", ink).replace("currentColor", ink)
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def bureau_seal_svg(
    uid: str = "seal",
    paper_hex: str = "#FFFFFF",
    ink: str = "#2b2b2b",
    numeral: str = "",
) -> str:
    """B/W bureau seal; numerals are supported only for on-screen preview."""
    safe_uid = "".join(char if char.isalnum() else "-" for char in uid)
    ring_id = f"bureau-ring-{safe_uid}"
    numeral = numeral if numeral in ROMAN_NUMERALS else ""
    center_mark = numeral or "P"
    mark_size = 34 if len(center_mark) == 1 else 28 if len(center_mark) == 2 else 24
    letter_spacing = "1.2" if numeral else "0"
    return f"""
<svg class="tw-card-back__seal" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <path id="{ring_id}" d="M 50 50 m -36,0 a 36,36 0 1,1 72,0 a 36,36 0 1,1 -72,0"/>
  </defs>
  <circle cx="50" cy="50" r="43" fill="{paper_hex}" stroke="{ink}" stroke-width="1.7"/>
  <circle cx="50" cy="50" r="34" fill="none" stroke="{ink}" stroke-width="0.9"/>
  <text font-family="IBM Plex Mono, DejaVu Sans Mono, monospace" font-size="5.3" letter-spacing="0.36" fill="{ink}">
    <textPath href="#{ring_id}" startOffset="0">{SEAL_RING_TEXT}</textPath>
  </text>
  <text x="50" y="52" font-family="Playfair Display, DejaVu Serif, Georgia, serif" font-weight="800" font-size="{mark_size}" letter-spacing="{letter_spacing}" text-anchor="middle" dominant-baseline="central" fill="{ink}">{center_mark}</text>
</svg>
""".strip()


def card_back_css(cfg: dict, token: str, target: str = "preview") -> str:
    """CSS port of simplified-ui's back using one assigned BACK ink in PDF."""
    use_cmyk = cfg["print"].get("use_cmyk", True)
    ink = device_cmyk(cfg, "back") if target == "pdf" and use_cmyk else preview_hex(cfg, "back")
    pattern_uri = pattern_data_uri(token, ink)
    paper = paper_stock(cfg["card"]["paper"])
    paper_color = css_from_hex(paper["hex"], target, use_cmyk)
    print_w = cfg["print"]["card_w_mm"]
    print_h = cfg["print"]["card_h_mm"]
    back_background = paper_color if target == "pdf" else (
        "radial-gradient(ellipse at 50% 42%, rgba(255,255,255,0.55) 0%, "
        f"rgba(255,255,255,0) 58%), {paper_color}"
    )
    back_shadow = "none" if target == "pdf" else (
        "0 2px 6px rgba(0,0,0,0.30), 0 6px 18px rgba(0,0,0,0.25), "
        "inset 0 1px 0 rgba(255,255,255,0.55)"
    )
    print_radius_mm = (
        max(0.0, float(cfg["print"].get("corner_radius_mm", 3.0)))
        if cfg["print"].get("round_corners", False)
        else 0.0
    )
    print_radius = f"{print_radius_mm:.2f}mm" if print_radius_mm else "0"
    print_inner_radius = f"{max(0.0, print_radius_mm - 1.0):.2f}mm" if print_radius_mm else "0"
    return f"""
.tw-card-back {{
  position:relative;
  overflow:hidden;
  background:{back_background};
  border:2px solid {ink};
  border-radius:12px;
  box-shadow:{back_shadow};
  font-family:'DejaVu Serif', Georgia, serif;
}}
.tw-card-back--hand {{ width:234px; height:327px; }}
.tw-card-back--verdict {{ width:140px; height:190px; }}
.tw-card-back--print {{ width:{print_w}mm; height:{print_h}mm; border-radius:{print_radius}; }}
.tw-card-back::before {{
  content:''; position:absolute; inset:4px; z-index:1; pointer-events:none;
  border:0.8px solid {ink}; border-radius:10px;
}}
.tw-card-back::after {{
  content:''; position:absolute; inset:7px; z-index:1; pointer-events:none;
  border:0.6px solid {ink}; border-radius:9px;
}}
.tw-card-back--print::before,
.tw-card-back--print::after {{ border-radius:{print_inner_radius}; }}
.tw-card-back__pattern {{
  position:absolute; inset:0; z-index:0; pointer-events:none;
  background-image:url('{pattern_uri}');
  background-repeat:repeat; background-size:auto; opacity:0.10;
}}
.tw-card-back__seal-wrap {{
  position:absolute; left:50%; top:50%; width:72%; aspect-ratio:1;
  transform:translate(-50%,-50%); z-index:2; pointer-events:none;
}}
.tw-card-back__seal {{ width:100%; height:100%; display:block; }}
.tw-card-back__id {{
  position:absolute; right:5px; top:4px; z-index:2;
  color:{ink}; font:5pt 'DejaVu Sans Mono','Courier New',monospace;
}}
"""


def render_card_back_html(
    *,
    cfg: dict,
    token: str,
    size: str = "verdict",
    card_id: str = "",
    uid: str = "",
    preview_numeral: str = "",
    target: str = "preview",
) -> str:
    """Render a card back; preview numerals are never supplied by print pages."""
    resolved = _resolved_token(token)
    id_html = f'<span class="tw-card-back__id">{card_id}</span>' if card_id else ""
    paper = paper_stock(cfg["card"]["paper"])
    use_cmyk = cfg["print"].get("use_cmyk", True)
    paper_color = css_from_hex(paper["hex"], target, use_cmyk)
    ink = device_cmyk(cfg, "back") if target == "pdf" and use_cmyk else preview_hex(cfg, "back")
    seal = bureau_seal_svg(
        uid=uid or card_id or "preview",
        paper_hex=paper_color,
        ink=ink,
        numeral=preview_numeral,
    )
    return f"""
<div class="tw-card-back tw-card-back--{size}" data-texture="{resolved}">
  <div class="tw-card-back__pattern" aria-hidden="true"></div>
  <div class="tw-card-back__seal-wrap">{seal}</div>
  {id_html}
</div>
""".strip()


def render_card_back_preview_html(
    cfg: dict,
    token: str,
    size: str,
    numeral: str = "",
) -> str:
    card = render_card_back_html(
        cfg=cfg,
        token=token,
        size=size,
        preview_numeral=numeral,
    )
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:16px; background:#d7d4ce; }}
{card_back_css(cfg, token)}
</style></head><body>{card}</body></html>"""
