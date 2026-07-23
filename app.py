"""P-Hacker Card Tweaker — entry point.

Single pipeline: tune chart + card params, preview the REAL card look
(same HTML/CSS as the print PDF), reduce the chart family into six minimal
die-face SVGs, then export YAML, SVG, and print-ready CMYK PDF assets.

Uses Streamlit's multipage `st.navigation`/`st.Page`. Normal keyed widgets own
the live values; render and export collect those values into a config snapshot.
See README.md for the full picture.
"""

from __future__ import annotations

import streamlit as st

from lib.card_back_render import card_back_label, card_back_tokens
from lib.config_io import dump_yaml, load_defaults, load_from_yaml_text
from lib.editor_state import current_config, initialize_editor, load_config_into_widgets

st.set_page_config(
    page_title="P-Hacker Card Tweaker",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_editor(load_defaults())


def _import_config() -> None:
    """Replace normal widget state once when a new YAML file is uploaded."""
    uploaded = st.session_state.get("cfg_upload")
    if uploaded is None:
        return
    load_config_into_widgets(load_from_yaml_text(uploaded.getvalue().decode("utf-8")))
    st.session_state["_config_imported"] = True


with st.sidebar:
    st.title("🃏 P-Hacker Card Tweaker")
    st.caption("Tune charts → preview cards → export dice SVGs, hypothesis cards, YAML, and print-ready CMYK PDF.")

    st.file_uploader(
        "Import config YAML", type=["yaml", "yml"], key="cfg_upload", on_change=_import_config,
    )
    if st.session_state.pop("_config_imported", False):
        st.success("Config loaded.")

    st.divider()

    st.subheader("🃏 Card Chrome")
    st.selectbox("Paper stock", ["white", "cream", "manila"], key="card_paper")
    st.slider("Band height %", 14, 30, key="band_pct")
    st.slider(
        "Chart opacity", 0.1, 1.0, step=0.05, key="card_chart_opacity",
        help="Real shipped value is 0.6 — the chart is background texture, not the focal point.",
    )
    st.checkbox("Typewriter footer (n=/p=)", key="card_show_footer")
    st.checkbox("Bureau stamp", key="card_show_stamp")
    st.checkbox("Fold creases", key="card_show_creases")
    st.caption("Screen atmosphere (never part of print geometry)")
    st.checkbox("Screen shadows", key="card_screen_shadows")
    st.checkbox("Paper texture", key="card_screen_paper_texture")
    st.checkbox("Warm crease tint", key="card_screen_warm_creases")

    st.subheader("🂠 Card Back")
    st.selectbox(
        "SVG motif", card_back_tokens(), key="card_back_texture", format_func=card_back_label,
        help="Real assets copied from phacker-game experiment/simplified-ui.",
    )

    st.divider()

pages = [
    st.Page("pages/chart_lab.py", title="Chart Lab", icon="📊", default=True),
    st.Page("pages/dice_svg.py", title="Dice SVG", icon="🎲"),
    st.Page("pages/ink_lab.py", title="Ink Lab", icon="🎨"),
    st.Page("pages/card_preview.py", title="Card Preview", icon="🃏"),
    st.Page("pages/hypothesis_cards.py", title="Hypothesis Cards", icon="🗂️"),
    st.Page("pages/print_atlas.py", title="Print Atlas & PDF", icon="🖨️"),
    st.Page("pages/config_page.py", title="Config", icon="⚙️"),
]
pg = st.navigation(pages)

with st.sidebar:
    yaml_text = dump_yaml(current_config())
    st.download_button(
        "📥 Export YAML", yaml_text, "phacker_card_config.yaml", "text/yaml",
        width="stretch",
        help="Back this up into gquinche/phacker-game under tools/card-art/.",
    )

pg.run()
