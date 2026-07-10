"""Card Preview — the full real-card-look gallery: every chart type, both
findings, rendered through the exact same HTML/CSS template used by the
print PDF (lib/card_render.py). This is the page to check "does this match
the real game" against phacker-game's DataCardPrint.tsx / game-cards.css.
"""
from __future__ import annotations

import streamlit as st

from lib import card_render
from lib import chart_generators as cg
from lib.card_render import render_preview_html
from lib.colors import cmyk_to_hex

st.title("🃏 Card Preview")
st.caption(
    "Every chart type at the real card size/band/opacity — the same template that feeds the "
    "print PDF, just rendered with hex colors here since browsers don't understand device-cmyk()."
)

cfg = st.session_state.cfg

with st.sidebar:
    st.subheader("Card Preview")
    cfg["card"]["show_footer"] = st.checkbox("Show typewriter footer (n=/p=)", cfg["card"]["show_footer"])
    cfg["card"]["show_stamp"] = st.checkbox("Show bureau stamp", cfg["card"]["show_stamp"])
    cfg["card"]["show_creases"] = st.checkbox("Show fold creases", cfg["card"]["show_creases"])
    size = st.radio("Card size", ["verdict", "hand"], horizontal=True,
                     help="verdict = 140x190px (publication blotter) · hand = 220x300px (hand strip)")

e_hex = cmyk_to_hex(*cfg["cmyk"]["effect"])
n_hex = cmyk_to_hex(*cfg["cmyk"]["no_effect"])


@st.fragment
def gallery():
    seed = st.number_input("Seed (same seed used for every chart type below)", 0, 9999, 0, 1)
    cards_html = []
    for name in cg.all_chart_names():
        svg_t = cg.render_svg_bare(name, True, int(seed), cfg, e_hex)
        svg_f = cg.render_svg_bare(name, False, int(seed), cfg, n_hex)
        cards_html.append(card_render.render_card_html(
            card_id=f"{name}-T", significant=True, chart_svg=svg_t, cfg=cfg, size=size))
        cards_html.append(card_render.render_card_html(
            card_id=f"{name}-F", significant=False, chart_svg=svg_f, cfg=cfg, size=size))
    html = render_preview_html(cards_html, cfg, gap_px=14)
    card_h = 300 if size == "hand" else 190
    st.iframe(html, height=card_h + 80)


gallery()

st.divider()
st.caption(
    "Cross-check against the real component: src/components/game/DataCardPrint.tsx + "
    "src/styles/game-cards.css (.print-card family) on gquinche/phacker-game, branch "
    "experiment/simplified-ui."
)
