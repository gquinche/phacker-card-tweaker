"""Paper-sheet preview and PDF export from ordinary keyed widget values.

The browser and PDF share one mm-based atlas layout. The browser target uses
hex colors; the PDF target applies device-CMYK when enabled. No fragment or
render cache sits between a slider value and the generated output.
"""
from __future__ import annotations

import streamlit as st

from lib import chart_generators as cg
from lib.card_render import render_print_atlas_html
from lib.config_io import PAGE_SIZES_MM, dump_yaml
from lib.pdf_pipeline import PdfPipelineError, PdfRendererUnavailable, build_pdf_bytes
from lib.editor_state import current_config
from lib.ink_control import PAGE_LABELS, audit_print_html

st.title("🖨️ Print Atlas & PDF")
st.caption(
    "The browser-safe HTML is the source of truth. The PDF button prints that same "
    "document, then optionally applies CMYK conversion in Python."
)

with st.sidebar:
    st.subheader("Page layout")
    c1, c2 = st.columns(2)
    with c1:
        st.number_input("Columns", 1, 8, step=1, key="print_cols")
    with c2:
        st.number_input("Rows", 1, 8, step=1, key="print_rows")
    st.selectbox(
        "Page size", list(PAGE_SIZES_MM.keys()), key="print_page",
        format_func=lambda value: value.replace("_", " ").title(),
    )

    st.subheader("Card size")
    cc1, cc2 = st.columns(2)
    with cc1:
        st.number_input("Width (mm)", 25.0, 80.0, step=0.01, key="print_card_w_mm")
    with cc2:
        st.number_input("Height (mm)", 40.0, 120.0, step=0.01, key="print_card_h_mm")
    st.number_input("Bleed (mm)", 0.0, 5.0, step=0.5, key="print_bleed_mm")

    st.subheader("Cutting")
    round_corners = st.checkbox(
        "Render rounded corners in print",
        key="print_round_corners",
        help="Off keeps straight cut lines; round the finished cards later with a physical corner cutter.",
    )
    st.number_input(
        "Corner radius (mm)",
        0.5,
        8.0,
        step=0.5,
        key="print_corner_radius_mm",
        disabled=not round_corners,
    )

    st.subheader("Color")
    st.checkbox(
        "Write true CMYK into the PDF", key="print_use_cmyk",
        help="The browser-safe HTML is rendered first; Python then runs the optional vector-preserving CMYK pass.",
    )
    st.selectbox(
        "PDF renderer",
        ["auto", "browser", "weasyprint"],
        key="print_pdf_renderer",
        format_func=lambda value: {
            "auto": "Auto (browser first)",
            "browser": "Chromium / Playwright",
            "weasyprint": "WeasyPrint fallback",
        }[value],
        help="Auto uses a browser-grade print renderer when Chromium is available, then falls back to WeasyPrint.",
    )
    st.text_input(
        "CMYK ICC profile path (optional)",
        key="print_cmyk_profile_path",
        help="Use the exact profile supplied by the print shop; otherwise Ghostscript uses its standard CMYK conversion.",
    )
    st.checkbox("Calibration strip (for print-scale checks)", key="print_show_calibration_strip")
    st.checkbox("Card ID stamps", key="print_show_card_id")
    st.checkbox("Include matching SVG card-back sheets", key="print_include_back_pages")
    st.checkbox(
        "Block PDF when foreign inks are detected",
        key="print_strict_ink_check",
        help="Runs page-level CMYK policy checks before WeasyPrint.",
    )

# Collect after declaring the page-specific controls so this snapshot includes
# exactly what the user sees in the widgets.
cfg = current_config()
p = cfg["print"]
cell_w = p["card_w_mm"] + p["bleed_mm"] * 2
cell_h = p["card_h_mm"] + p["bleed_mm"] * 2
page_w, page_h = PAGE_SIZES_MM[p["page"]]
fit_cols = int(page_w // cell_w)
fit_rows = int(page_h // cell_h)
st.info(
    f"Cell {cell_w:.1f}×{cell_h:.1f} mm on a {page_w:.0f}×{page_h:.0f} mm page — "
    f"fits up to {fit_cols}×{fit_rows} = {fit_cols * fit_rows} cards/page "
    f"(currently {p['cols']}×{p['rows']} = {p['cols'] * p['rows']})."
)

effect_hex = cfg["palette"]["SIG"]
no_effect_hex = cfg["palette"]["NULL"]
seed_count = int(cfg["seeds_per_type"])
effect_svgs = [
    cg.render_svg_bare(name, True, seed, cfg, effect_hex)
    for name in cg.all_chart_names()
    for seed in range(seed_count)
]
no_effect_svgs = [
    cg.render_svg_bare(name, False, seed, cfg, no_effect_hex)
    for name in cg.all_chart_names()
    for seed in range(seed_count)
]

st.subheader("Paper preview")
st.caption("White sheets are the physical paper area; optional back sheets use the selected real-game SVG motif.")
preview_html = render_print_atlas_html(cfg, effect_svgs, no_effect_svgs)
st.iframe(preview_html, height="content")

# The PDF source is literally the same HTML string shown above. This is the
# parity guarantee: no second target-specific layout or positioning pass.
pdf_html = preview_html
ink_audit = audit_print_html(pdf_html, cfg)
st.subheader("Ink preflight")
if ink_audit["safe"]:
    st.success("Generated print markup matches every page's allowed CMYK channels.")
else:
    st.error(f"Detected {len(ink_audit['warnings'])} foreign-ink condition(s).")
    for warning in ink_audit["warnings"]:
        st.warning(warning.message)

observed_rows = []
for page, counts in ink_audit["observed"].items():
    observed_rows.append({"Page": PAGE_LABELS[page], **counts})
st.dataframe(observed_rows, hide_index=True, width="stretch")

st.divider()
col_info, col_btn = st.columns([3, 1])
with col_info:
    st.markdown(f"""
| Setting | Value |
|---|---|
| EFFECT ink | `{effect_hex}` (C{cfg['cmyk']['effect'][0]} M{cfg['cmyk']['effect'][1]} Y{cfg['cmyk']['effect'][2]} K{cfg['cmyk']['effect'][3]}) |
| NO EFFECT ink | `{no_effect_hex}` (C{cfg['cmyk']['no_effect'][0]} M{cfg['cmyk']['no_effect'][1]} Y{cfg['cmyk']['no_effect'][2]} K{cfg['cmyk']['no_effect'][3]}) |
| BACK ink | `{cfg['palette']['BACK']}` (C{cfg['cmyk']['back'][0]} M{cfg['cmyk']['back'][1]} Y{cfg['cmyk']['back'][2]} K{cfg['cmyk']['back'][3]}) |
| PDF renderer | {p.get('pdf_renderer', 'auto')} |
| CMYK profile | {p.get('cmyk_profile_path') or 'Ghostscript default'} |
| Ink preflight | {'SAFE' if ink_audit['safe'] else 'BLOCKED'} |
| Card | {p['card_w_mm']}×{p['card_h_mm']} mm + {p['bleed_mm']}mm bleed |
| Print corners | {f"rounded · {p['corner_radius_mm']}mm" if p['round_corners'] else 'square · straight cut'} |
| Grid | {p['cols']}×{p['rows']} on {p['page'].replace('_', ' ')} |
| Card back | `{cfg['card']['back_texture']}` · neutral P seal · {'included' if p['include_back_pages'] else 'not included'} |
| Faces | {len(cg.all_chart_names())} chart types × {seed_count} seeds = {len(effect_svgs)} distinct cards/finding |
""")
with col_btn:
    if st.button("🖶 Generate PDF", type="primary", width="stretch"):
        if p.get("strict_ink_check", True) and not ink_audit["safe"]:
            st.error("PDF blocked: resolve the Ink preflight warnings or disable strict checking.")
        else:
            try:
                with st.spinner("Rendering the print-ready PDF…"):
                    st.session_state["_last_pdf"] = build_pdf_bytes(
                        pdf_html,
                        renderer=p.get("pdf_renderer", "auto"),
                        use_cmyk=p.get("use_cmyk", True),
                        profile_path=p.get("cmyk_profile_path") or None,
                    )
                    st.session_state["_last_pdf_config"] = dump_yaml(cfg)
                st.success(f"PDF ready — {len(st.session_state['_last_pdf']) // 1024} KB")
            except PdfRendererUnavailable as exc:
                st.error(
                    f"The selected PDF renderer is unavailable: {exc}. "
                    "Choose Auto or WeasyPrint, or install Chromium/Playwright."
                )
            except PdfPipelineError as exc:
                st.error(f"PDF/CMYK processing failed: {exc}")
            except Exception as exc:  # noqa: BLE001 — surface the real error to the user
                st.error(f"PDF generation failed: {exc}")

if "_last_pdf" in st.session_state:
    if st.session_state.get("_last_pdf_config") == dump_yaml(cfg):
        st.download_button(
            "📥 Download PDF", st.session_state["_last_pdf"], "phacker-print-cards.pdf",
            "application/pdf", width="stretch",
        )
    else:
        st.info("Settings changed since the last PDF. Generate it again before downloading.")

with st.expander("CMYK recipe (hand this to the litografía)"):
    effect, no_effect, back = (
        cfg["cmyk"]["effect"],
        cfg["cmyk"]["no_effect"],
        cfg["cmyk"]["back"],
    )
    st.code(
        "# P-Hacker CMYK Recipe\n"
        f"EFFECT_CMYK    = ({effect[0]/100:.3f}, {effect[1]/100:.3f}, {effect[2]/100:.3f}, {effect[3]/100:.3f})\n"
        f"NO_EFFECT_CMYK = ({no_effect[0]/100:.3f}, {no_effect[1]/100:.3f}, {no_effect[2]/100:.3f}, {no_effect[3]/100:.3f})\n"
        f"BACK_CMYK      = ({back[0]/100:.3f}, {back[1]/100:.3f}, {back[2]/100:.3f}, {back[3]/100:.3f})\n"
        f"EFFECT_HEX     = \"{effect_hex}\"\nNO_EFFECT_HEX  = \"{no_effect_hex}\"\nBACK_HEX       = \"{cfg['palette']['BACK']}\"\n"
        f"CARD = {p['card_w_mm']} x {p['card_h_mm']} mm | BLEED = {p['bleed_mm']} mm\n"
        f"GRID = {p['cols']} x {p['rows']}",
        language="text",
    )
