"""Interactive per-page CMYK recipes and channel-policy controls."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from lib.editor_state import current_config
from lib.ink_control import (
    CHANNELS,
    PAGE_KEYS,
    PAGE_LABELS,
    allowed_channels,
    channel_rows,
    ck_plane_rows,
    device_cmyk,
    preview_hex,
)

st.title("🎨 Ink Lab")
st.caption(
    "Assign one CMYK recipe and allowed channel set to each printed page. "
    "The Cyan–Black plane is a clickable M=0 / Y=0 slice; use the exact sliders for all four channels."
)

page = st.selectbox(
    "Printed page",
    PAGE_KEYS,
    format_func=lambda value: PAGE_LABELS[value],
    key="ink_lab_page",
)
key_prefix = "no_effect" if page == "no_effect" else page
channel_keys = {channel: f"{key_prefix}_{channel.lower()}" for channel in CHANNELS}
policy_key = f"{key_prefix}_allowed_channels"

cfg = current_config()
plane = pd.DataFrame(ck_plane_rows(step=5))
selector = alt.selection_point(
    name="ink_pick",
    fields=["C", "K"],
    on="click",
    clear=False,
)
base = (
    alt.Chart(plane)
    .mark_square(size=150)
    .encode(
        x=alt.X("C:Q", title="Cyan coverage (%)", scale=alt.Scale(domain=[0, 100])),
        y=alt.Y("K:Q", title="Black coverage (%)", scale=alt.Scale(domain=[100, 0])),
        color=alt.Color("hex:N", scale=None, legend=None),
        tooltip=["label:N", "hex:N"],
        opacity=alt.condition(selector, alt.value(1), alt.value(0.76)),
        stroke=alt.condition(selector, alt.value("#e11d48"), alt.value("#ffffff")),
        strokeWidth=alt.condition(selector, alt.value(3), alt.value(0.35)),
    )
    .add_params(selector)
)
event = st.altair_chart(
    base,
    key=f"ink_plane_{page}",
    on_select="rerun",
    selection_mode="ink_pick",
    use_container_width=True,
)
selected = event.selection.get("ink_pick", []) if event else []
if selected:
    picked = selected[-1] if isinstance(selected, list) else selected
    if isinstance(picked, dict) and "C" in picked and "K" in picked:
        st.session_state[channel_keys["C"]] = int(picked["C"])
        st.session_state[channel_keys["K"]] = int(picked["K"])

st.caption("Exact recipe")
columns = st.columns(4)
for column, channel in zip(columns, CHANNELS):
    with column:
        st.slider(channel, 0, 100, key=channel_keys[channel])

st.multiselect(
    "Allowed channels on this page",
    CHANNELS,
    key=policy_key,
    help="Strict preflight warns or blocks when rendered colors activate channels outside this set.",
)

cfg = current_config()
recipe = cfg["cmyk"][page]
hex_value = preview_hex(cfg, page)
st.html(
    f'<div style="display:flex;align-items:center;gap:10px;padding:8px 10px;border:1px solid #d4d4d8;border-radius:6px">'
    f'<span style="width:34px;height:34px;border-radius:4px;background:{hex_value};border:1px solid #999"></span>'
    f'<code>{PAGE_LABELS[page]} · C{recipe[0]} M{recipe[1]} Y{recipe[2]} K{recipe[3]} · {hex_value}</code></div>'
)
st.code(device_cmyk(cfg, page), language="css")

forbidden_active = [
    channel
    for channel, value in zip(CHANNELS, recipe)
    if value > 0 and channel not in allowed_channels(cfg, page)
]
if forbidden_active:
    st.warning(
        f"{PAGE_LABELS[page]} currently activates forbidden channels: "
        + ", ".join(forbidden_active)
    )
else:
    st.success(f"{PAGE_LABELS[page]} recipe matches its allowed-channel policy.")

st.divider()
st.subheader("CMYK channel histogram")
histogram = pd.DataFrame(channel_rows(cfg))
chart = (
    alt.Chart(histogram)
    .mark_bar()
    .encode(
        x=alt.X("channel:N", title="Ink channel", sort=list(CHANNELS)),
        y=alt.Y("coverage:Q", title="Coverage (%)", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("page:N", title="Printed page"),
        opacity=alt.condition("datum.allowed", alt.value(1), alt.value(0.32)),
        column=alt.Column("page:N", title=None),
        tooltip=["page:N", "channel:N", "coverage:Q", "allowed:N"],
    )
    .properties(width=150, height=220)
)
st.altair_chart(chart, use_container_width=True)
st.caption(
    "The histogram shows assigned recipe coverage. Print Atlas runs a second audit against the actual generated HTML/PDF markup and identifies foreign color literals by page."
)
