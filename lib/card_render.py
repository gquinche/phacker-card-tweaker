"""The single HTML/CSS card template — this IS the "single pipeline" the whole
rewrite is about. One template renders:
  (a) the live on-screen preview (embedded via st.html, real browser, hex colors)
  (b) the print-ready PDF atlas (fed to WeasyPrint, CMYK colors via device-cmyk())

Layout/proportions/structure are IDENTICAL between (a) and (b) — only the color
*expression* differs, because browsers don't understand CSS device-cmyk() but
WeasyPrint (v67+) does. That split is the one deliberate exception to "single
template"; everything else (sizes, band %, chart opacity, wash alpha, footer,
stamp, creases) is shared.

Mirrors, class-name-for-class-name where practical, the real game's
src/styles/game-cards.css .print-card family and the print-atlas calibrator
prototype (p-hacker-print-atlas-calibrator-v8.html) that proved this approach
out.
"""

from __future__ import annotations

import re

from .colors import cmyk_to_hex, hex_to_rgba_css
from .config_io import PAGE_SIZES_MM
from .pseudo_stats import footer_text

PAPER_STOCKS = {
    "cream": {"hex": "#F2ECE0", "edge": "#D9CFB9"},
    "white": {"hex": "#FFFFFF", "edge": "#D9D9D9"},
    "manila": {"hex": "#EFE7D2", "edge": "#CDBE9A"},
}

_COLOR_ATTR_RE = re.compile(r'(fill|stroke)="#[0-9a-fA-F]{6,8}"')
_COLOR_STYLE_RE = re.compile(r"(fill|stroke):\s*#[0-9a-fA-F]{6,8}")


def recolor_svg_to_currentcolor(svg_text: str, ink_hex: str) -> str:
    """Replace the baked finding-hex in a rendered chart SVG with `currentColor`.

    Mirrors tools/card-art/bake_card_svgs.py's strip_colors_to_currentcolor()
    exactly (same two regexes) so this stays a drop-in match with the real
    pipeline's "PRECOLOR=False" mode. Used here specifically to let the PDF
    path cascade a CSS device-cmyk() color into the chart's ink via a
    currentColor-aware wrapper, since matplotlib itself has no CMYK concept.
    """
    ink_hex = ink_hex.lower()

    def _repl_attr(m: re.Match) -> str:
        return m.group(0).split("=")[0] + '="currentColor"' if ink_hex in m.group(0).lower() else m.group(0)

    svg_text = _COLOR_ATTR_RE.sub(_repl_attr, svg_text)
    svg_text = _COLOR_STYLE_RE.sub(
        lambda m: (m.group(1) + ": currentColor") if ink_hex in m.group(0).lower() else m.group(0),
        svg_text,
    )
    return svg_text


def ink_css_color(cfg: dict, significant: bool, target: str) -> str:
    """Return the CSS color for the band/wash/chart ink.

    target="preview" -> hex (what every browser understands).
    target="pdf"      -> device-cmyk(c% m% y% k%) when cfg.print.use_cmyk is on
                         (WeasyPrint v67+ writes this straight into the PDF as
                         literal CMYK — no ICC profile needed for this to work),
                         else falls back to the same hex the preview uses.
    """
    key = "effect" if significant else "no_effect"
    c, m, y, k = cfg["cmyk"][key]
    if target == "pdf" and cfg["print"].get("use_cmyk", True):
        return f"device-cmyk({c}% {m}% {y}% {k}%)"
    return cmyk_to_hex(c, m, y, k)


CARD_CSS = """
.tw-card {{
  position: relative;
  background: {paper_hex};
  border-radius: 4px;
  border: 1px solid {paper_edge};
  box-shadow: 0 2px 6px rgba(0,0,0,0.30), 0 6px 18px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,240,0.55);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: {serif_stack};
  background-image:
    radial-gradient(ellipse 35% 35% at 0% 0%, rgba(140,110,60,0.30), transparent 70%),
    radial-gradient(ellipse 35% 35% at 100% 0%, rgba(140,110,60,0.25), transparent 70%),
    radial-gradient(ellipse 40% 40% at 0% 100%, rgba(140,110,60,0.30), transparent 70%),
    radial-gradient(ellipse 40% 40% at 100% 100%, rgba(140,110,60,0.25), transparent 70%);
}}
.tw-card--hand {{ width: 220px; min-height: 300px; }}
.tw-card--verdict {{ width: 140px; min-height: 190px; }}
.tw-card--print {{ width: {print_w}mm; height: {print_h}mm; min-height: 0; }}

.tw-card__crease--h {{ position:absolute; left:0; right:0; top:50%; height:1px; background: rgba(160,130,80,0.12); z-index:0; }}
.tw-card__crease--v {{ position:absolute; top:0; bottom:0; left:50%; width:1px; background: rgba(160,130,80,0.08); z-index:0; }}

.tw-card__band {{ position:relative; z-index:1; flex-shrink:0; display:flex; align-items:center; justify-content:center; padding: 4px 6px; }}
.tw-card--hand .tw-card__band, .tw-card--print .tw-card__band {{ height: {band_h_hand}; }}
.tw-card--verdict .tw-card__band {{ height: {band_h_verdict}; }}

.tw-card__band-label {{
  font-family: {print_font_stack};
  font-size: 0.75rem; font-weight: 700; letter-spacing: 0.22em;
  text-transform: uppercase; color: {paper_hex}; line-height: 1;
}}

.tw-card__plot {{ position:relative; z-index:1; flex:1; display:flex; padding: 6px 8px 8px; background: {paper_hex}; overflow: hidden; }}
.tw-card__wash {{ position:absolute; inset:0; background: {wash_css}; z-index: 0; }}
.tw-card__chart {{ position:relative; z-index:1; flex:1; width:100%; display:flex; opacity: {chart_opacity}; }}
.tw-card__chart svg {{ width:100%; height:100%; display:block; }}

.tw-card__footer {{ position:relative; z-index:1; padding: 3px 6px 4px; border-top: 1px solid rgba(140,110,60,0.20); background: rgba(235,228,210,0.45); flex-shrink:0; }}
.tw-card__footer-rule {{ font-family: {typed_font_stack}; font-size:0.7rem; letter-spacing:0.16em; text-transform:uppercase; color: rgba(60,45,20,0.55); border-bottom:1px solid rgba(100,80,40,0.20); padding-bottom:1px; margin-bottom:1px; }}
.tw-card__footer-stats {{ font-family: {typed_font_stack}; font-size:0.8rem; color: rgba(40,30,10,0.80); letter-spacing:0.04em; line-height:1.3; }}

.tw-card__stamp {{ position:absolute; bottom:24px; right:4px; width:24px; height:14px; border:1.5px solid rgba(58,110,165,0.18); border-radius:2px; transform: rotate(-8deg); z-index:0; }}
.tw-card__id {{ position:absolute; bottom:2px; right:3px; font-size:5pt; font-family: {typed_font_stack}; color: rgba(0,0,0,0.18); z-index:1; }}
"""

_PREVIEW_FONT_IMPORT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&'
    'family=Special+Elite&display=swap" rel="stylesheet">'
)
_PREVIEW_SERIF = "'Playfair Display', Georgia, serif"
_PREVIEW_TYPED = "'Special Elite', 'Courier New', monospace"
# PDF path deliberately skips the Google Fonts fetch (no network dependency /
# latency inside PDF generation) and falls back to bundled system serif/mono —
# fine for a layout proof; swap for the real fonts at the final art stage.
_PDF_SERIF = "'DejaVu Serif', Georgia, serif"
_PDF_TYPED = "'DejaVu Sans Mono', 'Courier New', monospace"


def _css_for(cfg: dict, target: str) -> str:
    paper = PAPER_STOCKS.get(cfg["card"]["paper"], PAPER_STOCKS["cream"])
    band_h_hand = "44px" if target == "preview" else f'{cfg["print"]["card_h_mm"] * cfg["band_pct"] / 100:.2f}mm'
    return CARD_CSS.format(
        paper_hex=paper["hex"],
        paper_edge=paper["edge"],
        serif_stack=_PDF_SERIF if target == "pdf" else _PREVIEW_SERIF,
        print_font_stack=_PDF_SERIF if target == "pdf" else _PREVIEW_SERIF,
        typed_font_stack=_PDF_TYPED if target == "pdf" else _PREVIEW_TYPED,
        band_h_hand=band_h_hand,
        band_h_verdict="38px",
        chart_opacity=cfg["card"]["chart_opacity"],
        wash_css="none",  # per-card wash is set inline (depends on significant/null)
        print_w=cfg["print"]["card_w_mm"],
        print_h=cfg["print"]["card_h_mm"],
    )


def render_card_html(
    *,
    card_id: str,
    significant: bool,
    chart_svg: str,
    cfg: dict,
    target: str = "preview",
    size: str = "verdict",
) -> str:
    """Build ONE `.tw-card` element's markup (no surrounding <html>/<style> —
    callers wrap N of these with `_css_for()` once per page/preview)."""
    ink = ink_css_color(cfg, significant, target)
    wash_alpha = cfg["card"]["wash_alpha_sig"] if significant else cfg["card"]["wash_alpha_null"]
    if target == "pdf" and cfg["print"].get("use_cmyk", True):
        # Cascade the CMYK ink into the chart's baked-hex SVG via currentColor.
        finding_hex = cfg["palette"]["SIG"] if significant else cfg["palette"]["NULL"]
        chart_svg = recolor_svg_to_currentcolor(chart_svg, finding_hex)
        chart_style = f'color: {ink};'
        wash_css = ink  # device-cmyk() has no alpha channel; wash uses opacity below instead
        wash_opacity = wash_alpha
    else:
        chart_style = ""
        wash_css = hex_to_rgba_css_or_pass(ink, wash_alpha)
        wash_opacity = 1.0

    label = "TRUE" if significant else "FALSE"
    band_class = "significant" if significant else "null"
    size_class = f"tw-card--{size}" if target != "pdf" else "tw-card--print"

    footer_html = ""
    if cfg["card"].get("show_footer", True):
        footer_html = (
            '<div class="tw-card__footer">'
            '<div class="tw-card__footer-rule">P-HACKER · RECORDS BUREAU</div>'
            f'<div class="tw-card__footer-stats">{footer_text(card_id, significant)}</div>'
            "</div>"
        )
    stamp_html = '<div class="tw-card__stamp" aria-hidden="true"></div>' if cfg["card"].get("show_stamp", True) else ""
    creases_html = ""
    if cfg["card"].get("show_creases", True):
        creases_html = (
            '<div class="tw-card__crease--h" aria-hidden="true"></div>'
            '<div class="tw-card__crease--v" aria-hidden="true"></div>'
        )
    id_html = f'<span class="tw-card__id">{card_id}</span>' if cfg["print"].get("show_card_id", True) and target == "pdf" else ""

    return f"""
<div class="tw-card {size_class}" style="background: {PAPER_STOCKS.get(cfg['card']['paper'], PAPER_STOCKS['cream'])['hex']};">
  {creases_html}
  <div class="tw-card__band tw-card__band--{band_class}" style="background: {ink};">
    <span class="tw-card__band-label">{label}</span>
  </div>
  <div class="tw-card__plot">
    <div class="tw-card__wash" style="background: {wash_css}; opacity: {wash_opacity};"></div>
    <div class="tw-card__chart" style="{chart_style}">{chart_svg}</div>
  </div>
  {footer_html}
  {stamp_html}
  {id_html}
</div>
""".strip()


def hex_to_rgba_css_or_pass(color: str, alpha: float) -> str:
    """color is a hex string in preview mode (device-cmyk() never reaches here
    for the wash — pdf mode passes the flat ink through `opacity` instead,
    since device-cmyk() has no built-in alpha component)."""
    if color.startswith("#"):
        return hex_to_rgba_css(color, alpha)
    return color


def render_preview_html(cards_html: list[str], cfg: dict, gap_px: int = 18) -> str:
    """Wrap N card divs into one standalone HTML doc for st.html embedding."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
{_PREVIEW_FONT_IMPORT}
<style>
body {{ margin:0; padding: 16px; background:#2f2a24; display:flex; flex-wrap:wrap; gap:{gap_px}px; align-items:flex-start; }}
{_css_for(cfg, "preview")}
</style></head><body>
{''.join(cards_html)}
</body></html>"""


def render_print_atlas_html(cfg: dict, sig_svgs: list[str], null_svgs: list[str]) -> str:
    """Build the full print-ready multi-page HTML document: one page of TRUE
    cards, one page of FALSE cards, laid out on a CSS Grid sized in mm with
    bleed — same structure as the proven print-atlas-calibrator prototype,
    just built in Python so it can also be fed to WeasyPrint."""
    p = cfg["print"]
    page_w, page_h = PAGE_SIZES_MM[p["page"]]
    cw, ch, bleed = p["card_w_mm"], p["card_h_mm"], p["bleed_mm"]
    cell_w, cell_h = cw + bleed * 2, ch + bleed * 2
    cols, rows = int(p["cols"]), int(p["rows"])

    def build_page(significant: bool, svg_pool: list[str]) -> str:
        n = cols * rows
        cells = []
        for i in range(n):
            svg = svg_pool[i % len(svg_pool)]
            card_id = ("T" if significant else "F") + f"{i:02d}"
            card_html = render_card_html(
                card_id=card_id, significant=significant, chart_svg=svg,
                cfg=cfg, target="pdf",
            )
            cells.append(f'<div class="tw-cell">{card_html}</div>')
        cal_strip = ""
        if p.get("show_calibration_strip"):
            swatches = ["cyan", "magenta", "yellow", "black", "red", "green", "blue", "gray", "white"]
            sw = page_w / len(swatches)
            cal_strip = '<div class="tw-calstrip">' + "".join(
                f'<div style="background:{c};width:{sw:.1f}mm;height:7mm;"></div>' for c in swatches
            ) + "</div>"
        label = "TRUE (Significant)" if significant else "FALSE (Null)"
        return f"""
<section class="tw-page">
  <div class="tw-grid" style="grid-template-columns: repeat({cols}, {cell_w:.2f}mm); grid-template-rows: repeat({rows}, {cell_h:.2f}mm);">
    {''.join(cells)}
  </div>
  {cal_strip}
  <!-- {label} -->
</section>"""

    body = build_page(True, sig_svgs) + build_page(False, null_svgs)

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page {{ size: {page_w}mm {page_h}mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ margin: 0; }}
.tw-page {{ width: {page_w}mm; height: {page_h}mm; position: relative; page-break-after: always; }}
.tw-page:last-child {{ page-break-after: avoid; }}
.tw-grid {{
  display: grid;
  position: absolute;
  left: {(page_w - cols * cell_w) / 2:.2f}mm;
  top: {(page_h - rows * cell_h) / 2:.2f}mm;
  gap: 0;
}}
.tw-cell {{
  display: flex; align-items: center; justify-content: center;
  border: 0.3pt dashed rgba(0,0,0,.15);
}}
.tw-calstrip {{ position:absolute; bottom:0; left:0; right:0; display:flex; }}
{_css_for(cfg, "pdf")}
</style></head><body>
{body}
</body></html>"""


def build_pdf_bytes(html: str) -> bytes:
    """Render the print-atlas HTML to a real PDF via WeasyPrint.

    Lazily imported so the rest of the app works even where WeasyPrint's
    system libs (pango/cairo) aren't installed — only the PDF button fails,
    with a clear message, rather than the whole app crashing at import time.
    On Streamlit Community Cloud, packages.txt in this repo installs those
    libs automatically; locally see the README.
    """
    from weasyprint import HTML  # noqa: WPS433 (intentional lazy import)

    return HTML(string=html).write_pdf(output_intent="device-cmyk")
