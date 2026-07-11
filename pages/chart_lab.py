"""Chart Lab — tune each chart type with ordinary keyed Streamlit widgets.

Each interaction performs Streamlit's normal full rerun. Rendering and export
collect the current widget keys into one config snapshot; no fragment or cache
maintains a competing copy of slider state.
"""
from __future__ import annotations

import streamlit as st

from lib import card_render
from lib import chart_generators as cg
from lib.card_render import render_preview_html
from lib.chart_params import CHART_PARAM_SCHEMAS, cast_value
from lib.editor_state import current_config, param_widget_key

st.title("📊 Chart Lab")
st.caption(
    "Tune each chart type's hatch/params. Left = raw matplotlib chart (axes visible, "
    "for judging shape). Right = the exact real-card composite, both findings."
)

cfg = current_config()

HATCH_OPTS = ["///", "\\\\\\", "|||", "---", "+++", "xxx", "ooo", "...", "/", "\\", "|", "-"]
GAUSS_OPTS = ["/", "\\", "//", "\\\\", "|||", "---", "+++", "xxx"]

with st.sidebar:
    st.subheader("Global chart params")
    st.slider("Thumbnail DPI", 80, 220, step=10, key="dpi")
    st.slider("Hatch line weight", 0.5, 5.0, step=0.1, key="hatch_lw")

    st.subheader("Hatch fills (no solid infills — ink-saving rule)")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Bar control", HATCH_OPTS, key="hatch_bar_control")
        st.selectbox("Box control", HATCH_OPTS, key="hatch_box_control")
    with c2:
        st.selectbox("Bar treatment", HATCH_OPTS, key="hatch_bar_treatment")
        st.selectbox("Box treatment", HATCH_OPTS, key="hatch_box_treatment")
    st.selectbox(
        "Gaussian Group B hatch", GAUSS_OPTS, key="hatch_gauss",
        help="Keep sparse — Group A stays clean so the two-bell overlap doesn't get damaged.",
    )

    st.caption("CMYK recipes and channel policies are edited in Ink Lab.")

chart_name = st.selectbox("Chart type", cg.all_chart_names(), key="lab_chart_name")


def _render_param_controls(name: str) -> None:
    schema = CHART_PARAM_SCHEMAS.get(name)
    if not schema:
        return
    st.caption(f"{name} params")
    cols = st.columns(2)
    for i, (param_name, (_kind, dtype, lo, hi, step, _default, label)) in enumerate(schema.items()):
        lo_c = cast_value(dtype, lo)
        hi_c = cast_value(dtype, hi)
        step_c = cast_value(dtype, step)
        key = param_widget_key(name, param_name)
        with cols[i % 2]:
            st.slider(label, lo_c, hi_c, step=step_c, key=key)


seed = st.number_input("Seed", 0, 9999, 0, 1, key=f"seed_{chart_name}")
with st.expander("Chart params", expanded=True):
    _render_param_controls(chart_name)

# Collect once after all widgets exist. This exact snapshot drives every render
# below and is the same shape used by YAML/PDF export.
cfg = current_config()
effect_hex = cfg["palette"]["SIG"]
no_effect_hex = cfg["palette"]["NULL"]

raw_col, card_col = st.columns([1, 1])
with raw_col:
    st.caption("Raw matplotlib chart")
    rc1, rc2 = st.columns(2)
    with rc1:
        st.image(cg.render_png(chart_name, True, int(seed), cfg, effect_hex), caption="EFFECT", width="stretch")
    with rc2:
        st.image(cg.render_png(chart_name, False, int(seed), cfg, no_effect_hex), caption="NO EFFECT", width="stretch")
with card_col:
    st.caption("Real card look")
    svg_effect = cg.render_svg_bare(chart_name, True, int(seed), cfg, effect_hex)
    svg_no_effect = cg.render_svg_bare(chart_name, False, int(seed), cfg, no_effect_hex)
    card_effect = card_render.render_card_html(
        card_id=f"{chart_name}-E", significant=True, chart_svg=svg_effect, cfg=cfg,
    )
    card_no_effect = card_render.render_card_html(
        card_id=f"{chart_name}-N", significant=False, chart_svg=svg_no_effect, cfg=cfg,
    )
    st.iframe(render_preview_html([card_effect, card_no_effect], cfg), height=340)

st.divider()
with st.expander("📐 Seed sweep — see several variants of this chart type at once"):
    sweep_cols = st.columns(cfg["seeds_per_type"] * 2)
    for variant_seed in range(cfg["seeds_per_type"]):
        with sweep_cols[variant_seed * 2]:
            st.caption(f"EFFECT seed {variant_seed}")
            st.image(cg.render_png(chart_name, True, variant_seed, cfg, effect_hex), width="stretch")
        with sweep_cols[variant_seed * 2 + 1]:
            st.caption(f"NO EFFECT seed {variant_seed}")
            st.image(cg.render_png(chart_name, False, variant_seed, cfg, no_effect_hex), width="stretch")
