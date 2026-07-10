"""Print Atlas & PDF — configure the print sheet (page size, grid, bleed),
preview it live, and generate a real print-ready PDF via WeasyPrint with
true CMYK ink values written into the file (device-cmyk(), WeasyPrint>=67).

The preview and the PDF are built from the exact same
lib.card_render.render_print_atlas_html() — the only difference is the color
expression (hex for the on-screen preview, device-cmyk() for the PDF), since
no browser understands device-cmyk() but WeasyPrint does.
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from lib import chart_generators as cg
from lib.card_render import build_pdf_bytes, render_print_atlas_html
from lib.colors import cmyk_to_hex
from lib.config_io import PAGE_SIZES_MM, dump_yaml

st.title("🖨️ Print Atlas & PDF")
st.caption(
    "One page of TRUE cards, one page of FALSE cards, laid out with bleed. "
    "Same layout for the live preview below and the exported PDF."
)

cfg = st.session_state.cfg
p = cfg["print"]

with st.sidebar:
    st.subheader("Page layout")
    c1, c2 = st.columns(2)
    with c1:
        p["cols"] = st.number_input("Columns", 1, 8, int(p["cols"]))
    with c2:
        p["rows"] = st.number_input("Rows", 1, 8, int(p["rows"]))
    p["page"] = st.selectbox(
        "Page size", list(PAGE_SIZES_MM.keys()),
        list(PAGE_SIZES_MM.keys()).index(p["page"]),
        format_func=lambda k: k.replace("_", " ").title(),
    )

    st.subheader("Card size")
    cc1, cc2 = st.columns(2)
    with cc1:
        p["card_w_mm"] = st.number_input("Width (mm)", 25.0, 80.0, float(p["card_w_mm"]), 0.01)
    with cc2:
        p["card_h_mm"] = st.number_input("Height (mm)", 40.0, 120.0, float(p["card_h_mm"]), 0.01)
    p["bleed_mm"] = st.number_input("Bleed (mm)", 0.0, 5.0, float(p["bleed_mm"]), 0.5)

    st.subheader("Color")
    p["use_cmyk"] = st.checkbox(
        "Write true CMYK into the PDF (device-cmyk())", p["use_cmyk"],
        help="Needs weasyprint>=67. Off = plain RGB-approximation PDF (still same layout).",
    )
    p["show_calibration_strip"] = st.checkbox("Calibration strip (for print-scale checks)", p["show_calibration_strip"])
    p["show_card_id"] = st.checkbox("Card ID stamps", p["show_card_id"])

    zoom = st.slider("Preview zoom", 20, 100, 45, 5)

cell_w = p["card_w_mm"] + p["bleed_mm"] * 2
cell_h = p["card_h_mm"] + p["bleed_mm"] * 2
page_w, page_h = PAGE_SIZES_MM[p["page"]]
fit_cols = int(page_w // cell_w)
fit_rows = int(page_h // cell_h)
st.info(
    f"Cell {cell_w:.1f}×{cell_h:.1f} mm on a {page_w:.0f}×{page_h:.0f} mm page — "
    f"fits up to {fit_cols}×{fit_rows} = {fit_cols * fit_rows} cards/page "
    f"(currently set to {p['cols']}×{p['rows']} = {p['cols'] * p['rows']})."
)

e_hex = cmyk_to_hex(*cfg["cmyk"]["effect"])
n_hex = cmyk_to_hex(*cfg["cmyk"]["no_effect"])


@st.cache_data(show_spinner=False)
def _svg_pool(seeds_per_type: int, cfg_fingerprint: str, e_hex_: str, n_hex_: str):
    sig = [cg.render_svg(name, True, s, cfg, e_hex_) for name in cg.all_chart_names() for s in range(seeds_per_type)]
    nul = [cg.render_svg(name, False, s, cfg, n_hex_) for name in cg.all_chart_names() for s in range(seeds_per_type)]
    return sig, nul


# Cheap fingerprint so the cache invalidates when chart-affecting params change
# (cache key must be hashable; cfg itself has nested lists/dicts so we don't
# pass it directly). chart_params covers every chart type now, not just
# synthetic_control's old `syn` dict.
_fingerprint = f"{cfg['hatch']}{cfg['hatch_lw']}{cfg['chart_params']}{cfg['dpi']}"
sig_svgs, null_svgs = _svg_pool(int(cfg["seeds_per_type"]), _fingerprint, e_hex, n_hex)


@st.fragment
def atlas_preview():
    preview_html = render_print_atlas_html(cfg, sig_svgs, null_svgs)
    # Give the user a zero-dependency "print via browser" escape hatch too —
    # same trick the original calibrator prototype used, scoped to just this
    # iframe's own content via @media print + window.print().
    printable = preview_html.replace(
        "</body>",
        '<div style="position:fixed;top:8px;right:8px;z-index:99" class="no-print">'
        '<button onclick="window.print()" style="background:#426183;color:#fff;border:none;'
        'padding:8px 14px;border-radius:4px;cursor:pointer;font-family:sans-serif;font-size:12px;'
        'font-weight:700;">🖨 Print this atlas</button></div>'
        "<style>@media print { .no-print { display:none !important; } }</style></body>",
    )
    scaled = (
        f'<div style="transform:scale({zoom / 100});transform-origin:top left;'
        f'background:#2a2825;padding:20px;">{printable}</div>'
    )
    components.html(scaled, height=int(page_h * 3.78 * zoom / 100) + 120, scrolling=True)


atlas_preview()

st.divider()
col_info, col_btn = st.columns([3, 1])
with col_info:
    st.markdown(f"""
| Setting | Value |
|---|---|
| TRUE ink | `{e_hex}` (device-cmyk: C{cfg['cmyk']['effect'][0]} M{cfg['cmyk']['effect'][1]} Y{cfg['cmyk']['effect'][2]} K{cfg['cmyk']['effect'][3]}) |
| FALSE ink | `{n_hex}` (device-cmyk: C{cfg['cmyk']['no_effect'][0]} M{cfg['cmyk']['no_effect'][1]} Y{cfg['cmyk']['no_effect'][2]} K{cfg['cmyk']['no_effect'][3]}) |
| Card | {p['card_w_mm']}×{p['card_h_mm']} mm + {p['bleed_mm']}mm bleed |
| Grid | {p['cols']}×{p['rows']} on {p['page'].replace('_', ' ')} |
| Faces | {len(cg.all_chart_names())} chart types × {cfg['seeds_per_type']} seeds = {len(sig_svgs)} distinct cards/finding |
""")
with col_btn:
    if st.button("🖶 Generate PDF", type="primary", width="stretch"):
        try:
            with st.spinner("Rendering the print-ready PDF…"):
                html = render_print_atlas_html(cfg, sig_svgs, null_svgs)
                pdf_bytes = build_pdf_bytes(html)
            st.session_state["_last_pdf"] = pdf_bytes
            st.success(f"PDF ready — {len(pdf_bytes) // 1024} KB")
        except ImportError:
            st.error(
                "WeasyPrint isn't available in this environment (missing system libraries "
                "like pango/cairo). On Streamlit Community Cloud this is handled automatically "
                "by packages.txt in this repo. Locally, see README.md → Local setup."
            )
        except Exception as exc:  # noqa: BLE001 — surface the real error to the user
            st.error(f"PDF generation failed: {exc}")

if "_last_pdf" in st.session_state:
    st.download_button(
        "📥 Download PDF", st.session_state["_last_pdf"], "phacker-print-cards.pdf",
        "application/pdf", width="stretch",
    )

with st.expander("CMYK recipe (hand this to the litografía)"):
    e, n = cfg["cmyk"]["effect"], cfg["cmyk"]["no_effect"]
    st.code(
        "# P-Hacker CMYK Recipe\n"
        f"TRUE_CMYK  = ({e[0]/100:.3f}, {e[1]/100:.3f}, {e[2]/100:.3f}, {e[3]/100:.3f})\n"
        f"FALSE_CMYK = ({n[0]/100:.3f}, {n[1]/100:.3f}, {n[2]/100:.3f}, {n[3]/100:.3f})\n"
        f"TRUE_HEX   = \"{e_hex}\"\nFALSE_HEX  = \"{n_hex}\"\n"
        f"CARD = {p['card_w_mm']} x {p['card_h_mm']} mm | BLEED = {p['bleed_mm']} mm\n"
        f"GRID = {p['cols']} x {p['rows']}",
        language="text",
    )
