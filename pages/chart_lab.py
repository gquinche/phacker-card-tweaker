"""Chart Lab — tune each chart type's params; see the raw chart AND the real
card look for both findings side by side. The live-render panel is an
@st.fragment so tuning one chart type doesn't force a full-page rerun.

Every chart type has its own tunable-params panel, rendered generically from
lib/chart_params.CHART_PARAM_SCHEMAS — not just synthetic_control. That's
what lets km_curve (restored — see lib/chart_generators.py module docstring)
get dialed into something that reads as general science texture instead of
staying dropped for looking too clinical.
"""
from __future__ import annotations

import streamlit as st

from lib import card_render
from lib import chart_generators as cg
from lib.card_render import render_preview_html
from lib.chart_params import CHART_PARAM_SCHEMAS, cast_value
from lib.colors import cmyk_to_hex

st.title("📊 Chart Lab")
st.caption(
    "Tune each chart type's hatch/params. Left = raw matplotlib chart (axes visible, "
    "for judging shape). Right = the exact real-card composite, both findings."
)

cfg = st.session_state.cfg

HATCH_OPTS = ["///", "\\\\\\", "|||", "---", "+++", "xxx", "ooo", "...", "/", "\\", "|", "-"]
GAUSS_OPTS = ["/", "\\", "//", "\\\\", "|||", "---", "+++", "xxx"]

with st.sidebar:
    st.subheader("Global chart params")
    cfg["dpi"] = st.slider("Thumbnail DPI", 80, 220, int(cfg["dpi"]), 10)
    cfg["hatch_lw"] = st.slider("Hatch line weight", 0.5, 5.0, float(cfg["hatch_lw"]), 0.1)

    st.subheader("Hatch fills (no solid infills — ink-saving rule)")
    c1, c2 = st.columns(2)
    with c1:
        cfg["hatch"]["bar"][0] = st.selectbox("Bar control", HATCH_OPTS, HATCH_OPTS.index(cfg["hatch"]["bar"][0]))
        cfg["hatch"]["box"][0] = st.selectbox("Box control", HATCH_OPTS, HATCH_OPTS.index(cfg["hatch"]["box"][0]))
    with c2:
        cfg["hatch"]["bar"][1] = st.selectbox("Bar treatment", HATCH_OPTS, HATCH_OPTS.index(cfg["hatch"]["bar"][1]))
        cfg["hatch"]["box"][1] = st.selectbox("Box treatment", HATCH_OPTS, HATCH_OPTS.index(cfg["hatch"]["box"][1]))
    gi = GAUSS_OPTS.index(cfg["hatch"]["gauss"]) if cfg["hatch"]["gauss"] in GAUSS_OPTS else 0
    cfg["hatch"]["gauss"] = st.selectbox(
        "Gaussian Group B hatch", GAUSS_OPTS, gi,
        help="Keep sparse — Group A stays clean so the two-bell overlap doesn't get damaged.",
    )

    st.subheader("Ink — EFFECT / TRUE (blue)")
    e = cfg["cmyk"]["effect"]
    ec1, ec2 = st.columns(2)
    with ec1:
        e[0] = st.slider("C", 0, 100, e[0], key="e_c")
        e[1] = st.slider("M", 0, 100, e[1], key="e_m")
    with ec2:
        e[2] = st.slider("Y", 0, 100, e[2], key="e_y")
        e[3] = st.slider("K", 0, 100, e[3], key="e_k")
    e_hex = cmyk_to_hex(*e)
    st.html(f'<div style="background:{e_hex};border-radius:4px;padding:4px 8px;'
            f'font-family:monospace;font-size:12px;color:#fff">{e_hex}</div>')

    st.subheader("Ink — NO EFFECT / FALSE (gray)")
    n = cfg["cmyk"]["no_effect"]
    nc1, nc2 = st.columns(2)
    with nc1:
        n[0] = st.slider("C", 0, 100, n[0], key="n_c")
        n[1] = st.slider("M", 0, 100, n[1], key="n_m")
    with nc2:
        n[2] = st.slider("Y", 0, 100, n[2], key="n_y")
        n[3] = st.slider("K", 0, 100, n[3], key="n_k")
    n_hex = cmyk_to_hex(*n)
    st.html(f'<div style="background:{n_hex};border-radius:4px;padding:4px 8px;'
            f'font-family:monospace;font-size:12px;color:#fff">{n_hex}</div>')
    cfg["palette"]["SIG"] = e_hex
    cfg["palette"]["NULL"] = n_hex

chart_name = st.selectbox("Chart type", cg.all_chart_names(), key="lab_chart_name")


def _render_param_controls(name: str, key_prefix: str) -> None:
    """Generic per-chart params panel, driven by CHART_PARAM_SCHEMAS — every
    chart type gets one of these, not just synthetic_control."""
    schema = CHART_PARAM_SCHEMAS.get(name)
    if not schema:
        return
    params = cfg["chart_params"].setdefault(name, {})
    st.caption(f"{name} params")
    cols = st.columns(2)
    for i, (key, (kind, dtype, lo, hi, step, default, label)) in enumerate(schema.items()):
        lo_c, hi_c, step_c = cast_value(dtype, lo), cast_value(dtype, hi), cast_value(dtype, step)
        current = params.get(key, default)
        with cols[i % 2]:
            if kind == "range":
                cur = (cast_value(dtype, current[0]), cast_value(dtype, current[1]))
                params[key] = list(st.slider(label, lo_c, hi_c, cur, step_c, key=f"{key_prefix}_{name}_{key}"))
            else:
                params[key] = st.slider(label, lo_c, hi_c, cast_value(dtype, current), step_c, key=f"{key_prefix}_{name}_{key}")


@st.fragment
def chart_panel(name: str):
    seed = st.number_input("Seed", 0, 9999, 0, 1, key=f"seed_{name}")

    with st.expander("Chart params", expanded=True):
        _render_param_controls(name, "param")

    e_hex_local = cmyk_to_hex(*cfg["cmyk"]["effect"])
    n_hex_local = cmyk_to_hex(*cfg["cmyk"]["no_effect"])

    raw_col, card_col = st.columns([1, 1])
    with raw_col:
        st.caption("Raw matplotlib chart")
        rc1, rc2 = st.columns(2)
        with rc1:
            st.image(cg.render_png(name, True, int(seed), cfg, e_hex_local), caption="TRUE", width="stretch")
        with rc2:
            st.image(cg.render_png(name, False, int(seed), cfg, n_hex_local), caption="FALSE", width="stretch")
    with card_col:
        st.caption("Real card look (same chart embedded in the actual print-card composite)")
        svg_true = cg.render_svg(name, True, int(seed), cfg, e_hex_local)
        svg_false = cg.render_svg(name, False, int(seed), cfg, n_hex_local)
        card_true = card_render.render_card_html(card_id=f"{name}-T", significant=True, chart_svg=svg_true, cfg=cfg)
        card_false = card_render.render_card_html(card_id=f"{name}-F", significant=False, chart_svg=svg_false, cfg=cfg)
        html = render_preview_html([card_true, card_false], cfg)
        st.iframe(html, height=340)


chart_panel(chart_name)

st.divider()
with st.expander("📐 Seed sweep — see several variants of this chart type at once"):
    e_hex2 = cmyk_to_hex(*cfg["cmyk"]["effect"])
    n_hex2 = cmyk_to_hex(*cfg["cmyk"]["no_effect"])
    sweep_cols = st.columns(cfg["seeds_per_type"] * 2)
    for s in range(cfg["seeds_per_type"]):
        with sweep_cols[s * 2]:
            st.caption(f"TRUE seed {s}")
            st.image(cg.render_png(chart_name, True, s, cfg, e_hex2), width="stretch")
        with sweep_cols[s * 2 + 1]:
            st.caption(f"FALSE seed {s}")
            st.image(cg.render_png(chart_name, False, s, cfg, n_hex2), width="stretch")
