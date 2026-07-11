"""Config — full YAML overview, reset-to-defaults, and where this goes in
phacker-game once it's dialed in."""
from __future__ import annotations

import streamlit as st

from lib.config_io import dump_yaml, load_defaults
from lib.editor_state import replace_config, schedule_config_draft_reset

st.title("⚙️ Config")
cfg = st.session_state.cfg

st.markdown(
    "This YAML is the single source of tunable values for both the card look and the print "
    "atlas — chart hatch/params, CMYK ink, card-composite ratios, and page/grid layout. "
    "Export it (sidebar, on every page) and back it up into "
    "`gquinche/phacker-game/tools/card-art/` — the notebook's *TWEAK HERE* cell "
    "(`PALETTE`, `fc.SYN`, `fc.HATCH`) reads the same value names, so it's a direct copy, "
    "not a translation."
)

col1, col2 = st.columns([3, 1])
with col1:
    st.code(dump_yaml(cfg), language="yaml")
with col2:
    st.download_button(
        "📥 Export YAML", dump_yaml(cfg), "phacker_card_config.yaml", "text/yaml",
        width="stretch",
    )
    if st.button("↺ Reset to defaults", width="stretch"):
        # This button runs after the shared sidebar widgets. Defer draft cleanup
        # to the next full run so Streamlit never mutates instantiated widgets.
        replace_config(load_defaults(), clear_drafts=False)
        schedule_config_draft_reset()
        st.rerun()

st.divider()
st.subheader("Where this plugs into phacker-game")
st.markdown(
    "- **Chart hatch / synthetic-control params** → `tools/card-art/fake_charts_cardart.py` "
    "module-level `HATCH` / `SYN` dicts, or override them from the notebook's tweak cell "
    "(`fc.HATCH.update(...)`, `fc.SYN.update(...)`).\n"
    "- **Palette (SIG/NULL hex)** → the notebook's `PALETTE` dict, and "
    "`tools/card-art/bake_card_svgs.py`'s `SIG`/`NULL` constants.\n"
    "- **band_pct / chart_opacity / wash alphas** → `src/styles/game-cards.css` "
    "(`.print-card__band` height, `.print-card__chart` opacity, "
    "`.print-card--significant/--null .print-card__plot` wash alpha).\n"
    "- **Print card size / bleed / grid** → whatever you hand to the litografía "
    "alongside the exported PDF — this tool doesn't write into the game repo for you, "
    "by design, since these are print-shop-facing, not game-code values."
)
