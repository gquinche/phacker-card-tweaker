"""Config — full YAML overview, reset-to-defaults, and where this goes in
phacker-game once it's dialed in."""
from __future__ import annotations

import streamlit as st

from lib.config_io import dump_yaml, load_defaults
from lib.editor_state import current_config, load_config_into_widgets

st.title("⚙️ Config")
cfg = current_config()

st.markdown(
    "This YAML is the single source of tunable values for the card look, dice SVGs, and print "
    "atlas — chart hatch/params, six die faces, CMYK ink, card-composite ratios, and page/grid layout. "
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
    st.button(
        "↺ Reset to defaults", width="stretch",
        on_click=load_config_into_widgets, args=(load_defaults(),),
    )

st.divider()
st.subheader("Where this plugs into phacker-game")
st.markdown(
    "- **Chart hatch / synthetic-control params** → `tools/card-art/fake_charts_cardart.py` "
    "module-level `HATCH` / `SYN` dicts, or override them from the notebook's tweak cell "
    "(`fc.HATCH.update(...)`, `fc.SYN.update(...)`).\n"
    "- **Palette (SIG/NULL/BACK hex)** → derived from the three page CMYK recipes; "
    "SIG/NULL still map to the notebook and bake constants.\n"
    "- **band_pct / chart_opacity / wash alphas** → `src/styles/game-cards.css` "
    "(`.print-card__band` height, `.print-card__chart` opacity, "
    "`.print-card--significant/--null .print-card__plot` wash alpha).\n"
    "- **Card-back texture** → `public/patterns/` + `SealedCardBack.tsx` on "
    "`experiment/simplified-ui`; this app embeds local copies for offline PDF output.\n"
    "- **Dice faces / background / color toggle** → the standalone SVG ZIP from Dice SVG; "
    "these settings stay in the shared YAML so the six-face set is reproducible.\n"
    "- **Print card size / bleed / grid** → whatever you hand to the litografía "
    "alongside the exported PDF — this tool doesn't write into the game repo for you, "
    "by design, since these are print-shop-facing, not game-code values."
)
