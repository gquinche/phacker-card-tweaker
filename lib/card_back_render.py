"""Render the real simplified-UI card-back SVG options offline.

The motif files are copied verbatim from phacker-game's
`experiment/simplified-ui/public/patterns`. The game applies them as CSS masks;
for browser + WeasyPrint parity here, we recolor the SVG ink and embed it as a
repeating data-URI background at the same low contrast.
"""
from __future__ import annotations

import base64
from pathlib import Path

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


def card_back_css(cfg: dict, token: str) -> str:
    """CSS port of simplified-ui's sealed-card-back treatment."""
    pattern_uri = pattern_data_uri(token)
    print_w = cfg["print"]["card_w_mm"]
    print_h = cfg["print"]["card_h_mm"]
    return f"""
.tw-card-back {{
  position:relative;
  overflow:hidden;
  background:
    radial-gradient(ellipse at 50% 42%, rgba(255,250,235,0.55) 0%, rgba(242,236,224,0) 58%),
    linear-gradient(160deg, #F5F0E4 0%, #F2ECE0 100%);
  border:2px solid #2b2b2b;
  border-radius:12px;
  box-shadow:0 2px 6px rgba(0,0,0,0.30), 0 6px 18px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,250,235,0.55);
  font-family:'DejaVu Serif', Georgia, serif;
}}
.tw-card-back--hand {{ width:234px; height:327px; }}
.tw-card-back--verdict {{ width:140px; height:190px; }}
.tw-card-back--print {{ width:{print_w}mm; height:{print_h}mm; }}
.tw-card-back::before {{
  content:''; position:absolute; inset:4px; z-index:1; pointer-events:none;
  border:0.8px solid #b1924e; border-radius:10px;
}}
.tw-card-back::after {{
  content:''; position:absolute; inset:7px; z-index:1; pointer-events:none;
  border:0.6px solid rgba(43,43,43,0.5); border-radius:9px;
}}
.tw-card-back__pattern {{
  position:absolute; inset:0; z-index:0; pointer-events:none;
  background-image:url('{pattern_uri}');
  background-repeat:repeat; background-size:auto; opacity:0.10;
}}
.tw-card-back__cartouche {{
  position:absolute; left:50%; top:50%; width:52%; height:30%;
  transform:translate(-50%,-54%); z-index:1; pointer-events:none;
  background:#F2ECE0; border:1.6px solid #2b2b2b; border-radius:12px;
}}
.tw-card-back__cartouche::before {{
  content:''; position:absolute; inset:4px; border:0.7px solid #b1924e; border-radius:2px;
}}
.tw-card-back__cartouche::after {{
  content:''; position:absolute; inset:10px; pointer-events:none;
  background:
    linear-gradient(#2b2b2b,#2b2b2b) left top / 1px 8px no-repeat,
    linear-gradient(#2b2b2b,#2b2b2b) left top / 8px 1px no-repeat,
    linear-gradient(#2b2b2b,#2b2b2b) right top / 1px 8px no-repeat,
    linear-gradient(#2b2b2b,#2b2b2b) right top / 8px 1px no-repeat,
    linear-gradient(#2b2b2b,#2b2b2b) left bottom / 1px 8px no-repeat,
    linear-gradient(#2b2b2b,#2b2b2b) left bottom / 8px 1px no-repeat,
    linear-gradient(#2b2b2b,#2b2b2b) right bottom / 1px 8px no-repeat,
    linear-gradient(#2b2b2b,#2b2b2b) right bottom / 8px 1px no-repeat;
}}
.tw-card-back__numeral {{
  position:absolute; left:50%; top:50%; transform:translate(-50%,-58%);
  z-index:2; color:#2b2b2b; font-size:22px; font-weight:700; letter-spacing:2px;
}}
.tw-card-back__label {{
  position:absolute; left:50%; bottom:8px; transform:translateX(-50%); z-index:2;
  color:rgba(117,117,117,0.55); font-family:'DejaVu Sans Mono','Courier New',monospace;
  font-size:8px; letter-spacing:0.35em; text-transform:uppercase; white-space:nowrap;
}}
.tw-card-back__id {{
  position:absolute; right:5px; top:4px; z-index:2;
  color:rgba(43,43,43,0.35); font:5pt 'DejaVu Sans Mono','Courier New',monospace;
}}
"""


def render_card_back_html(
    *,
    cfg: dict,
    token: str,
    size: str = "verdict",
    numeral: str = "I",
    card_id: str = "",
) -> str:
    """Render one card-back element using the chosen real SVG motif."""
    resolved = _resolved_token(token)
    numeral = numeral if numeral in ROMAN_NUMERALS else "I"
    id_html = f'<span class="tw-card-back__id">{card_id}</span>' if card_id else ""
    return f"""
<div class="tw-card-back tw-card-back--{size}" data-texture="{resolved}">
  <div class="tw-card-back__pattern" aria-hidden="true"></div>
  <div class="tw-card-back__cartouche" aria-hidden="true"></div>
  <div class="tw-card-back__numeral">{numeral}</div>
  <div class="tw-card-back__label">P HACKER GAME</div>
  {id_html}
</div>
""".strip()


def render_card_back_preview_html(cfg: dict, token: str, size: str, numeral: str) -> str:
    card = render_card_back_html(cfg=cfg, token=token, size=size, numeral=numeral)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:16px; background:#d7d4ce; }}
{card_back_css(cfg, token)}
</style></head><body>{card}</body></html>"""
