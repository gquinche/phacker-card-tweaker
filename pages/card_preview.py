"""Individual card gallery rendered from the current keyed widget settings."""
from __future__ import annotations

import streamlit as st

from lib import card_render
from lib import chart_generators as cg
from lib.card_back_render import ROMAN_NUMERALS, render_card_back_preview_html
from lib.card_render import render_preview_html
from lib.editor_state import current_config

st.title("🃏 Card Preview")
st.caption(
    "Individual cards at the real card size/band/opacity. For paper placement, "
    "use Print Atlas & PDF — its preview now mirrors the final sheet layout."
)

cfg = current_config()

with st.sidebar:
    st.subheader("Card Preview")
    size = st.radio(
        "Card size", ["verdict", "hand"], horizontal=True, key="preview_card_size",
        help="verdict = 140x190px (publication blotter) · hand = 234x327px (hand strip)",
    )
    preview_numeral = st.selectbox(
        "Preview-only Roman numeral",
        ["None", *ROMAN_NUMERALS],
        key="preview_back_numeral",
        help="Replaces P for visual review only. Print/PDF backs always show P.",
    )

seed = st.number_input(
    "Seed (same seed used for every chart type below)", 0, 9999, 0, 1, key="preview_seed",
)
card_h = 327 if size == "hand" else 190

st.subheader("Selected card back")
st.iframe(
    render_card_back_preview_html(
        cfg,
        cfg["card"]["back_texture"],
        size,
        "" if preview_numeral == "None" else preview_numeral,
    ),
    height=card_h + 40,
)

st.subheader("Card fronts")
effect_hex = cfg["palette"]["SIG"]
no_effect_hex = cfg["palette"]["NULL"]
cards_html = []
for name in cg.all_chart_names():
    svg_effect = cg.render_svg_bare(name, True, int(seed), cfg, effect_hex)
    svg_no_effect = cg.render_svg_bare(name, False, int(seed), cfg, no_effect_hex)
    cards_html.append(card_render.render_card_html(
        card_id=f"{name}-E", significant=True, chart_svg=svg_effect, cfg=cfg, size=size,
    ))
    cards_html.append(card_render.render_card_html(
        card_id=f"{name}-N", significant=False, chart_svg=svg_no_effect, cfg=cfg, size=size,
    ))

st.iframe(render_preview_html(cards_html, cfg, gap_px=14), height=card_h + 80)

st.divider()
st.caption(
    "Cross-check against the real component: src/components/game/DataCardPrint.tsx + "
    "src/styles/game-cards.css (.print-card family) on gquinche/phacker-game, branch "
    "experiment/simplified-ui."
)
