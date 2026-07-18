"""The single HTML/CSS card template — this IS the "single pipeline" the whole
rewrite is about. One canonical HTML/CSS document renders both the live browser
preview and the downloadable PDF. Geometry, typography, SVGs, shadows, and
textures are authored once; Python only chooses the PDF engine and optionally
post-processes the finished PDF into CMYK.

The HTML stays browser-safe RGB so the preview is the visual source of truth.
This keeps print color policy from creating a second layout implementation.

Mirrors, class-name-for-class-name where practical, the real game's
src/styles/game-cards.css .print-card family and the print-atlas calibrator
prototype (p-hacker-print-atlas-calibrator-v8.html) that proved this approach
out.
"""

from __future__ import annotations

import re

from .card_back_render import card_back_css, card_back_label, render_card_back_html
from .config_io import PAGE_SIZES_MM
from .ink_control import preview_hex
from .paper import paper_stock
from .pseudo_stats import footer_text

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


def ink_css_color(cfg: dict, significant: bool, target: str = "preview") -> str:
    """Return the canonical browser-safe ink color.

    ``target`` remains accepted for compatibility with older callers, but color
    conversion is intentionally no longer mixed into HTML generation. The same
    RGB/hex source is used for the preview and PDF; Python converts the finished
    PDF in :mod:`lib.pdf_pipeline` when CMYK export is enabled.
    """
    del target
    page = "effect" if significant else "no_effect"
    return preview_hex(cfg, page)


CARD_CSS = """
.tw-card {{
  position: relative;
  background: {paper_hex};
  border-radius: 12px;                    /* matches simplified-ui --card-radius */
  border: 1px solid {paper_edge};
  box-shadow: none;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: {serif_stack};
  background-image: none;
}}
.tw-card--hand {{ width: 234px; height: 327px; min-height: 327px; }}    /* simplified-ui: 1.5× base portrait */
.tw-card--verdict {{ width: 140px; height: 190px; min-height: 190px; }}
.tw-card--print {{ width: {print_w}mm; height: {print_h}mm; min-height: 0; border-radius: {print_radius}; }}

.tw-card__crease--h {{ position:absolute; left:0; right:0; top:50%; height:1px; background: {crease_h}; z-index:0; }}
.tw-card__crease--v {{ position:absolute; top:0; bottom:0; left:50%; width:1px; background: {crease_v}; z-index:0; }}

.tw-card__band {{ position:relative; z-index:1; flex-shrink:0; display:flex; align-items:center; justify-content:center; padding: 4px 6px; }}
.tw-card--hand .tw-card__band {{ height: {band_h_hand}; }}
.tw-card--verdict .tw-card__band {{ height: {band_h_verdict}; }}
.tw-card--print .tw-card__band {{ height: {band_h_print}; }}
/* simplified-ui: hand band label is 1.08rem (1.5× base) */
.tw-card--hand .tw-card__band-label {{ font-size: 1.08rem; }}

.tw-card__band-label {{
  font-family: {print_font_stack};
  font-size: 0.75rem; font-weight: 700; letter-spacing: 0.22em;
  text-transform: uppercase; color: {paper_hex}; line-height: 1;
}}

.tw-card__plot {{ position:relative; z-index:1; flex:1; display:flex; padding: 6px 8px 8px; background: {paper_hex}; overflow: hidden; }}
.tw-card__chart {{ position:relative; z-index:1; flex:1; width:100%; display:flex; opacity: {chart_opacity}; }}
.tw-card__chart svg {{ width:100%; height:100%; display:block; }}

.tw-card__footer {{ position:relative; z-index:1; padding: 3px 6px 4px; border-top: 1px solid {footer_rule}; background: {footer_bg}; flex-shrink:0; }}
.tw-card__footer-rule {{ font-family: {typed_font_stack}; font-size:0.7rem; letter-spacing:0.16em; text-transform:uppercase; color: {footer_text}; border-bottom:1px solid {footer_rule}; padding-bottom:1px; margin-bottom:1px; }}
.tw-card__footer-stats {{ font-family: {typed_font_stack}; font-size:0.8rem; color: {footer_stats}; letter-spacing:0.04em; line-height:1.3; }}

.tw-card__stamp {{ position:absolute; bottom:24px; right:4px; width:24px; height:14px; border:1.5px solid {stamp_color}; border-radius:2px; transform: rotate(-8deg); z-index:0; }}
.tw-card__id {{ position:absolute; bottom:2px; right:3px; font-size:5pt; font-family: {typed_font_stack}; color: {id_color}; z-index:1; }}

/* Screen atmosphere is explicit and never changes print geometry or color
   source values. The PDF renderer receives the same base layout. */
@media screen {{
  .tw-card {{ box-shadow: {screen_card_shadow}; background-image: {screen_paper_texture}; }}
  .tw-card__crease--h {{ background: {screen_crease_h}; }}
  .tw-card__crease--v {{ background: {screen_crease_v}; }}
  .tw-card__footer {{ background: {screen_footer_bg}; border-top-color: {screen_footer_rule}; }}
  .tw-card__footer-rule {{ color: {screen_footer_text}; border-bottom-color: {screen_footer_rule}; }}
  .tw-card__footer-stats {{ color: {screen_footer_stats}; }}
  .tw-card__stamp {{ border-color: {screen_stamp_color}; }}
}}
"""

_FONT_IMPORT = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&'
    'family=Special+Elite&display=swap" rel="stylesheet">'
)
# One font stack for both targets. Browser-grade PDF rendering can load the
# same web fonts as the preview; local/system fallbacks keep the HTML usable
# when the font service is unavailable.
_SERIF = "'Playfair Display', Georgia, 'DejaVu Serif', serif"
_TYPED = "'Special Elite', 'Courier New', 'DejaVu Sans Mono', monospace"


def _css_for(cfg: dict, target: str = "preview") -> str:
    """Return one layout stylesheet with screen atmosphere layered on top.

    ``target`` is retained for compatibility with older callers. It no longer
    changes geometry, fonts, or source colors; only ``@media screen`` adds the
    optional atmosphere that belongs to the live preview.
    """
    del target
    paper = paper_stock(cfg["card"]["paper"])
    paper_hex = paper["hex"]
    paper_edge = paper["edge"]
    card_cfg = cfg["card"]
    screen_shadows = card_cfg.get("screen_shadows", True)
    screen_paper_texture = card_cfg.get("screen_paper_texture", True)
    screen_warm_creases = card_cfg.get("screen_warm_creases", True)

    # Keep hand cards at their shipped pixel height, but keep print cards in
    # millimetres for both the browser atlas and the final PDF.
    band_h_hand = "66px"
    band_h_print = f'{cfg["print"]["card_h_mm"] * cfg["band_pct"] / 100:.2f}mm'
    print_radius = (
        f'{max(0.0, float(cfg["print"].get("corner_radius_mm", 3.0))):.2f}mm'
        if cfg["print"].get("round_corners", False)
        else "0"
    )
    shadow = (
        "0 2px 6px rgba(0,0,0,0.30), 0 6px 18px rgba(0,0,0,0.25), "
        "inset 0 1px 0 rgba(255,255,240,0.55)"
        if screen_shadows else "none"
    )
    texture = (
        "radial-gradient(ellipse 35% 35% at 0% 0%, rgba(140,110,60,0.30), transparent 70%),"
        " radial-gradient(ellipse 35% 35% at 100% 0%, rgba(140,110,60,0.25), transparent 70%),"
        " radial-gradient(ellipse 40% 40% at 0% 100%, rgba(140,110,60,0.30), transparent 70%),"
        " radial-gradient(ellipse 40% 40% at 100% 100%, rgba(140,110,60,0.25), transparent 70%)"
        if screen_paper_texture else "none"
    )
    screen_crease_h = "rgba(160,130,80,0.12)" if screen_warm_creases else "rgba(0,0,0,0.12)"
    screen_crease_v = "rgba(160,130,80,0.08)" if screen_warm_creases else "rgba(0,0,0,0.08)"
    screen_footer_rule = "rgba(140,110,60,0.20)" if screen_warm_creases else "rgba(0,0,0,0.20)"
    screen_footer_bg = "rgba(235,228,210,0.45)" if screen_paper_texture else paper_hex
    screen_footer_text = "rgba(60,45,20,0.55)" if screen_warm_creases else "rgba(0,0,0,0.55)"
    screen_footer_stats = "rgba(40,30,10,0.80)" if screen_warm_creases else "rgba(0,0,0,0.80)"
    screen_stamp_color = "rgba(58,110,165,0.18)" if screen_warm_creases else "rgba(0,0,0,0.18)"

    return CARD_CSS.format(
        paper_hex=paper_hex,
        paper_edge=paper_edge,
        serif_stack=_SERIF,
        print_font_stack=_SERIF,
        typed_font_stack=_TYPED,
        band_h_hand=band_h_hand,
        band_h_verdict="38px",
        band_h_print=band_h_print,
        chart_opacity=cfg["card"]["chart_opacity"],
        print_w=cfg["print"]["card_w_mm"],
        print_h=cfg["print"]["card_h_mm"],
        print_radius=print_radius,
        crease_h="rgba(0,0,0,0.12)",
        crease_v="rgba(0,0,0,0.08)",
        footer_rule="rgba(0,0,0,0.20)",
        footer_bg=paper_hex,
        footer_text="rgba(0,0,0,0.55)",
        footer_stats="rgba(0,0,0,0.80)",
        stamp_color="rgba(0,0,0,0.18)",
        id_color="rgba(0,0,0,0.18)",
        screen_card_shadow=shadow,
        screen_paper_texture=texture,
        screen_crease_h=screen_crease_h,
        screen_crease_v=screen_crease_v,
        screen_footer_rule=screen_footer_rule,
        screen_footer_bg=screen_footer_bg,
        screen_footer_text=screen_footer_text,
        screen_footer_stats=screen_footer_stats,
        screen_stamp_color=screen_stamp_color,
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
    del target
    ink = ink_css_color(cfg, significant)
    # SVGs remain baked RGB/hex in the canonical document. The CMYK pass runs
    # after layout and converts the finished PDF, so chart geometry is shared.
    chart_style = ""

    label = "EFFECT" if significant else "NO EFFECT"
    band_class = "significant" if significant else "null"
    size_class = f"tw-card--{size}"

    footer_html = ""
    if cfg["card"].get("show_footer", False):
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
    id_html = (
        f'<span class="tw-card__id">{card_id}</span>'
        if cfg["print"].get("show_card_id", True) and size == "print"
        else ""
    )
    paper_color = paper_stock(cfg["card"]["paper"])["hex"]

    return f"""
<div class="tw-card {size_class}" style="background: {paper_color};">
  {creases_html}
  <div class="tw-card__band tw-card__band--{band_class}" style="background: {ink};">
    <span class="tw-card__band-label">{label}</span>
  </div>
  <div class="tw-card__plot">
    <div class="tw-card__chart" style="{chart_style}">{chart_svg}</div>
  </div>
  {footer_html}
  {stamp_html}
  {id_html}
</div>
""".strip()


def render_preview_html(cards_html: list[str], cfg: dict, gap_px: int = 18) -> str:
    """Wrap N card divs into one standalone HTML doc for st.html embedding."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
{_FONT_IMPORT}
<style>
body {{ margin:0; padding: 16px; background:#2f2a24; display:flex; flex-wrap:wrap; gap:{gap_px}px; align-items:flex-start; }}
{_css_for(cfg, "preview")}
</style></head><body>
{''.join(cards_html)}
</body></html>"""


def render_print_atlas_html(
    cfg: dict,
    sig_svgs: list[str],
    null_svgs: list[str],
    *,
    target: str = "preview",
) -> str:
    """Build the canonical atlas HTML used by preview and PDF rendering.

    ``target`` remains accepted for compatibility with older callers, but it
    no longer changes layout, typography, SVGs, or colors. Screen-only chrome
    is isolated in ``@media screen`` rules so the browser and PDF consume the
    same document.
    """
    if target not in {"preview", "pdf"}:
        raise ValueError(f"Unsupported atlas target: {target}")
    del target
    p = cfg["print"]
    page_w, page_h = PAGE_SIZES_MM[p["page"]]
    cw, ch, bleed = p["card_w_mm"], p["card_h_mm"], p["bleed_mm"]
    cell_w, cell_h = cw + bleed * 2, ch + bleed * 2
    cols, rows = int(p["cols"]), int(p["rows"])
    capacity = cols * rows
    if capacity < 1:
        raise ValueError("Print atlas rows and columns must produce at least one cell")
    if not sig_svgs or not null_svgs:
        raise ValueError("Print atlas requires at least one EFFECT and one NO EFFECT SVG")

    def build_page(
        significant: bool,
        svg_pool: list[str],
        start_index: int,
        total_count: int,
        sheet_number: int,
        sheet_count: int,
    ) -> str:
        n = len(svg_pool)
        cells = []
        for local_index, svg in enumerate(svg_pool):
            card_index = start_index + local_index
            card_id = ("E" if significant else "N") + f"{card_index:02d}"
            card_html = render_card_html(
                card_id=card_id,
                significant=significant,
                chart_svg=svg,
                cfg=cfg,
                size="print",
            )
            cells.append(f'<div class="tw-cell">{card_html}</div>')
        cal_strip = ""
        if p.get("show_calibration_strip"):
            swatches = ["cyan", "magenta", "yellow", "black", "red", "green", "blue", "gray", "white"]
            sw = page_w / len(swatches)
            cal_strip = '<div class="tw-calstrip">' + "".join(
                f'<div style="background:{c};width:{sw:.1f}mm;height:7mm;"></div>' for c in swatches
            ) + "</div>"
        page_key = "effect" if significant else "no_effect"
        title = "EFFECT CARDS" if significant else "NO EFFECT CARDS"
        subtitle = "SIGNIFICANT RESULTS" if significant else "NULL RESULTS"
        sheet_meta = f"{subtitle} · {total_count} CARDS · SHEET {sheet_number}/{sheet_count}"
        atlas_ink = ink_css_color(cfg, significant)
        grid_w = cols * cell_w
        grid_h = rows * cell_h
        grid_left = (page_w - grid_w) / 2
        grid_top = max((page_h - grid_h) / 2, 13.0)
        header_top = max(2.0, grid_top - 11.0)
        return f"""
<section class="tw-page" data-page="{page_key}">
  <header class="tw-atlas-header" style="left:{grid_left:.2f}mm; width:{grid_w:.2f}mm; top:{header_top:.2f}mm; color:{atlas_ink};">
    <span class="tw-atlas-header__kicker">P-HACKER · RECORDS BUREAU</span>
    <span class="tw-atlas-header__title">{title}</span>
    <span class="tw-atlas-header__meta">{sheet_meta}</span>
  </header>
  <div class="tw-grid" style="grid-template-columns: repeat({cols}, {cell_w:.2f}mm); grid-template-rows: repeat({rows}, {cell_h:.2f}mm); left:{grid_left:.2f}mm; top:{grid_top:.2f}mm;">
    {''.join(cells)}
  </div>
  {cal_strip}
</section>"""

    def build_back_page(
        uid_index: int,
        sheet_number: int,
        card_count: int,
        total_count: int,
        sheet_count: int,
    ) -> str:
        token = cfg["card"].get("back_texture", "tex-chevron")
        back_ink = preview_hex(cfg, "back")
        cells = []
        for i in range(card_count):
            card_html = render_card_back_html(
                cfg=cfg,
                token=token,
                size="print",
                uid=f"back-{uid_index}-{i}",
            )
            cells.append(f'<div class="tw-cell">{card_html}</div>')
        grid_w = cols * cell_w
        grid_h = rows * cell_h
        grid_left = (page_w - grid_w) / 2
        grid_top = max((page_h - grid_h) / 2, 13.0)
        header_top = max(2.0, grid_top - 11.0)
        return f"""
<section class="tw-page" data-page="back">
  <header class="tw-atlas-header tw-atlas-header--back" style="left:{grid_left:.2f}mm; width:{grid_w:.2f}mm; top:{header_top:.2f}mm; color:{back_ink};">
    <span class="tw-atlas-header__kicker">P-HACKER · RECORDS BUREAU</span>
    <span class="tw-atlas-header__title">CARD BACKS</span>
    <span class="tw-atlas-header__meta">{card_back_label(token).upper()} · {total_count} CARDS · SHEET {sheet_number}/{sheet_count}</span>
  </header>
  <div class="tw-grid" style="grid-template-columns: repeat({cols}, {cell_w:.2f}mm); grid-template-rows: repeat({rows}, {cell_h:.2f}mm); left:{grid_left:.2f}mm; top:{grid_top:.2f}mm;">
    {''.join(cells)}
  </div>
</section>"""

    front_sheets: list[tuple[bool, list[str], int, int, int]] = []
    for significant, svg_pool in ((True, sig_svgs), (False, null_svgs)):
        sheet_count = (len(svg_pool) + capacity - 1) // capacity
        for sheet_index, start in enumerate(range(0, len(svg_pool), capacity), start=1):
            front_sheets.append((
                significant,
                svg_pool[start:start + capacity],
                start,
                sheet_index,
                sheet_count,
            ))

    body = "".join(
        build_page(
            significant,
            sheet_svgs,
            start,
            len(sig_svgs if significant else null_svgs),
            sheet_number,
            sheet_count,
        )
        for significant, sheet_svgs, start, sheet_number, sheet_count in front_sheets
    )
    if p.get("include_back_pages", True):
        # One matching back sheet per front sheet for duplex/flip printing.
        body += "".join(
            build_back_page(
                global_sheet_number,
                sheet_number,
                len(sheet_svgs),
                len(sig_svgs if significant else null_svgs),
                sheet_count,
            )
            for global_sheet_number, (
                significant,
                sheet_svgs,
                _start,
                sheet_number,
                sheet_count,
            ) in enumerate(front_sheets, start=1)
        )
    font_import = _FONT_IMPORT
    body_class = "tw-preview-stage"
    page_background = "#FFFFFF"
    preview_stage_css = """
@media screen {
  body.tw-preview-stage {
    min-height:100vh;
    padding:10mm;
    display:flex;
    flex-direction:column;
    align-items:center;
    gap:10mm;
    background:#d7d4ce;
  }
  body.tw-preview-stage .tw-page {
    page-break-after:auto;
    box-shadow:0 2mm 7mm rgba(35,31,25,0.24);
    outline:0.25mm solid rgba(0,0,0,0.12);
  }
}
"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{font_import}<style>
@page {{ size: {page_w}mm {page_h}mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ margin: 0; }}
{preview_stage_css}
.tw-page {{
  width:{page_w}mm;
  height:{page_h}mm;
  position:relative;
  overflow:hidden;
  flex:0 0 auto;
  background:{page_background};
  page-break-after:always;
}}
.tw-page:last-child {{ page-break-after: avoid; }}
.tw-atlas-header {{
  position:absolute;
  z-index:2;
  display:grid;
  grid-template-columns: 1fr auto;
  align-items:end;
  gap:0 4mm;
  font-family:{_SERIF};
  border-bottom:0.35mm solid currentColor;
  padding-bottom:1.2mm;
}}
.tw-atlas-header__kicker {{
  grid-column:1 / -1;
  font-family:{_TYPED};
  font-size:2.1mm;
  letter-spacing:0.18em;
  font-weight:700;
}}
.tw-atlas-header__title {{
  font-size:5.4mm;
  font-weight:700;
  letter-spacing:0.06em;
  line-height:1;
}}
.tw-atlas-header__meta {{
  font-family:{_TYPED};
  font-size:2.1mm;
  letter-spacing:0.08em;
  white-space:nowrap;
}}
.tw-grid {{
  display: grid;
  position: absolute;
  gap: 0;
}}
.tw-cell {{
  display: flex; align-items: center; justify-content: center;
  border: 0.3pt dashed rgba(0,0,0,.15);
}}
.tw-calstrip {{ position:absolute; bottom:0; left:0; right:0; display:flex; }}
{_css_for(cfg)}
{card_back_css(cfg, cfg["card"].get("back_texture", "tex-chevron"))}
</style></head><body class="{body_class}">
{body}
</body></html>"""


def render_individual_card_pages_html(
    cfg: dict,
    cards: list[tuple[str, bool, str]],
) -> str:
    """Render one card-sized PDF page per front, followed by its optional back.

    The resulting page order is intentionally stable so :mod:`lib.pdf_pipeline`
    can split one efficient batch render into one PDF per card without relaying
    out the card or launching a browser once per file.
    """
    if not cards:
        raise ValueError("Individual PDF export requires at least one card")

    p = cfg["print"]
    bleed = float(p["bleed_mm"])
    page_w = float(p["card_w_mm"]) + bleed * 2
    page_h = float(p["card_h_mm"]) + bleed * 2
    token = cfg["card"].get("back_texture", "tex-chevron")
    include_backs = bool(p.get("include_back_pages", True))
    pages = []

    for index, (card_id, significant, chart_svg) in enumerate(cards):
        card_html = render_card_html(
            card_id=card_id,
            significant=significant,
            chart_svg=chart_svg,
            cfg=cfg,
            size="print",
        )
        page_key = "effect" if significant else "no_effect"
        pages.append(
            f'<section class="tw-page" data-page="{page_key}" data-card-id="{card_id}">'
            f'<div class="tw-cell">{card_html}</div></section>'
        )
        if include_backs:
            back_html = render_card_back_html(
                cfg=cfg,
                token=token,
                size="print",
                uid=f"individual-back-{index}",
            )
            pages.append(
                f'<section class="tw-page" data-page="back" data-card-id="{card_id}">'
                f'<div class="tw-cell">{back_html}</div></section>'
            )

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_FONT_IMPORT}<style>
@page {{ size: {page_w:.2f}mm {page_h:.2f}mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ margin: 0; }}
.tw-page {{
  width:{page_w:.2f}mm;
  height:{page_h:.2f}mm;
  display:flex;
  align-items:center;
  justify-content:center;
  overflow:hidden;
  page-break-after:always;
}}
.tw-page:last-child {{ page-break-after:avoid; }}
.tw-cell {{
  width:100%;
  height:100%;
  display:flex;
  align-items:center;
  justify-content:center;
  border:0.3pt dashed rgba(0,0,0,.15);
}}
{_css_for(cfg)}
{card_back_css(cfg, token)}
</style></head><body>
{''.join(pages)}
</body></html>"""


def build_pdf_bytes(html: str, **kwargs) -> bytes:
    """Backward-compatible wrapper around the browser-first PDF pipeline."""
    from .pdf_pipeline import build_pdf_bytes as build_pipeline_pdf

    return build_pipeline_pdf(html, **kwargs)
