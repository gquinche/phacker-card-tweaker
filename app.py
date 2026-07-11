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
from lib.editor_state import clear_config_widget_drafts, hydrate_config_widget, replace_config

st.set_page_config(
    page_title="P-Hacker Card Tweaker",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="expanded",
)

if st.session_state.pop("_clear_config_widget_drafts", False):
    clear_config_widget_drafts()

if "cfg" not in st.session_state:
    st.session_state.cfg = load_defaults()


def _import_config() -> None:
    """Load YAML exactly once per upload event, then reset stale widget drafts."""
    uploaded = st.session_state.get("cfg_upload")
    if uploaded is None:
        return
    replace_config(load_from_yaml_text(uploaded.getvalue().decode("utf-8")))
    st.session_state["_config_imported"] = True


with st.sidebar:
    st.title("🃏 P-Hacker Card Tweaker")
    st.caption("Tune → preview the real card look → export YAML + a print-ready CMYK PDF.")

    st.file_uploader(
        "Import config YAML", type=["yaml", "yml"], key="cfg_upload", on_change=_import_config,
    )
    if st.session_state.pop("_config_imported", False):
        st.success("Config loaded.")

    st.divider()

    # Paper stock + card chrome — global controls, visible from every page.
    # Widget drafts are deliberately separate from cfg, so an imported/reset config
    # cannot be overwritten by stale page-local Streamlit values on the next rerun.
    st.subheader("🃏 Card Chrome")
    cfg = st.session_state.cfg
    paper_key = hydrate_config_widget("card_paper", cfg["card"]["paper"])
    band_key = hydrate_config_widget("band_pct", cfg["band_pct"])
    opacity_key = hydrate_config_widget("card_chart_opacity", cfg["card"]["chart_opacity"])
    footer_key = hydrate_config_widget("card_show_footer", cfg["card"]["show_footer"])
    stamp_key = hydrate_config_widget("card_show_stamp", cfg["card"]["show_stamp"])
    creases_key = hydrate_config_widget("card_show_creases", cfg["card"]["show_creases"])

    cfg["card"]["paper"] = st.selectbox("Paper stock", ["cream", "white", "manila"], key=paper_key)
    cfg["band_pct"] = st.slider("Band height %", 14, 30, key=band_key)
    cfg["card"]["chart_opacity"] = st.slider(
        "Chart opacity", 0.1, 1.0, step=0.05, key=opacity_key,
        help="Real shipped value is 0.6 — the chart is background texture, not the focal point.",
    )
    cfg["card"]["show_footer"] = st.checkbox("Typewriter footer (n=/p=)", key=footer_key)
    cfg["card"]["show_stamp"] = st.checkbox("Bureau stamp", key=stamp_key)
    cfg["card"]["show_creases"] = st.checkbox("Fold creases", key=creases_key)

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
