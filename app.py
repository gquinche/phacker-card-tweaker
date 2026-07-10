"""P-Hacker Card Tweaker — entry point.

Single pipeline: tune chart + card params, preview the REAL card look
(same HTML/CSS as the print PDF), then export (1) a YAML config to back up
into phacker-game/tools/card-art/ and (2) a print-ready CMYK PDF atlas.

Uses Streamlit's multipage `st.navigation`/`st.Page` (each page below owns one
concern) and `@st.fragment` inside the pages for snappy live-tuning without a
full-app rerun on every slider tweak. See README.md for the full picture.
"""

from __future__ import annotations

import streamlit as st

from lib.config_io import dump_yaml, load_defaults, load_from_yaml_text

st.set_page_config(
    page_title="P-Hacker Card Tweaker",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "cfg" not in st.session_state:
    st.session_state.cfg = load_defaults()

with st.sidebar:
    st.title("🃏 P-Hacker Card Tweaker")
    st.caption("Tune → preview the real card look → export YAML + a print-ready CMYK PDF.")

    uploaded = st.file_uploader("Import config YAML", type=["yaml", "yml"], key="cfg_upload")
    if uploaded is not None:
        st.session_state.cfg = load_from_yaml_text(uploaded.read().decode("utf-8"))
        st.success("Config loaded.")

    st.divider()

    # Paper stock + card chrome — global controls, visible from every page
    st.subheader("🃏 Card Chrome")
    cfg = st.session_state.cfg
    cfg["card"]["paper"] = st.selectbox(
        "Paper stock", ["cream", "white", "manila"],
        ["cream", "white", "manila"].index(cfg["card"]["paper"]),
    )
    cfg["band_pct"] = st.slider("Band height %", 14, 30, int(cfg["band_pct"]), 1)
    cfg["card"]["chart_opacity"] = st.slider(
        "Chart opacity", 0.1, 1.0, float(cfg["card"]["chart_opacity"]), 0.05,
        help="Real shipped value is 0.6 — the chart is background texture, not the focal point.",
    )
    cfg["card"]["show_footer"] = st.checkbox("Typewriter footer (n=/p=)", cfg["card"]["show_footer"])
    cfg["card"]["show_stamp"] = st.checkbox("Bureau stamp", cfg["card"]["show_stamp"])
    cfg["card"]["show_creases"] = st.checkbox("Fold creases", cfg["card"]["show_creases"])

    st.divider()

pages = [
    st.Page("pages/chart_lab.py", title="Chart Lab", icon="📊", default=True),
    st.Page("pages/card_preview.py", title="Card Preview", icon="🃏"),
    st.Page("pages/print_atlas.py", title="Print Atlas & PDF", icon="🖨️"),
    st.Page("pages/config_page.py", title="Config", icon="⚙️"),
]
pg = st.navigation(pages)

with st.sidebar:
    yaml_text = dump_yaml(st.session_state.cfg)
    st.download_button(
        "📥 Export YAML", yaml_text, "phacker_card_config.yaml", "text/yaml",
        width="stretch",
        help="Back this up into gquinche/phacker-game under tools/card-art/.",
    )

pg.run()
