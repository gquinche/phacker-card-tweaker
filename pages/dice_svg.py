"""Dice SVG — six bold chart contours for a physical die or credibility ladder."""
from __future__ import annotations

import streamlit as st

from lib import chart_generators as cg
from lib import dice_render
from lib.editor_state import current_config

st.title("🎲 Dice SVG")
st.caption(
    "Build six minimal chart glyphs that read from across the table. The geometry comes from "
    "the same 11-chart family as the cards, but exports without axes, labels, fills, hatches, "
    "or legends — just the recognizable contours."
)


def _restore_recommended_faces() -> None:
    for index, spec in enumerate(dice_render.DEFAULT_FACE_SPECS, start=1):
        st.session_state[f"dice_face_{index}_chart"] = spec["chart"]
        st.session_state[f"dice_face_{index}_significant"] = spec["significant"]
        st.session_state[f"dice_face_{index}_seed"] = spec["seed"]


with st.sidebar:
    st.subheader("Dice appearance")
    transparent_background = st.checkbox(
        "Transparent SVG background",
        key="dice_transparent_background",
        help=(
            "Enabled by default: exports no background fill or die frame, ready to import "
            "into Orca and convert into a texture. Only the graph contours remain."
        ),
    )
    st.color_picker(
        "Die background",
        key="dice_background",
        disabled=transparent_background,
        help="Used only when Transparent SVG background is unchecked.",
    )
    st.checkbox(
        "Use blue / gray outlines",
        key="dice_colored_outlines",
        help=(
            "On: EFFECT faces use the current blue ink and NO EFFECT faces use the current gray ink. "
            "Off: every face uses one neutral dark contour."
        ),
    )
    st.caption(
        "Blue and gray follow the live Ink Lab palette. Background color is used only when transparency is off."
    )
    st.button("Restore recommended six", on_click=_restore_recommended_faces, width="stretch")

st.subheader("Choose the six faces")
st.caption(
    "The starting set uses six distinct silhouettes: two Gaussians, box-and-whisker, bar, "
    "step curves, forest, and parallel trends. Every slot can instead use any chart in the full family."
)

chart_names = cg.all_chart_names()
face_columns = st.columns(3)
for index in range(1, dice_render.DICE_FACE_COUNT + 1):
    with face_columns[(index - 1) % 3]:
        with st.container(border=True):
            st.markdown(f"**Face {index}**")
            st.selectbox(
                "Chart",
                chart_names,
                key=f"dice_face_{index}_chart",
                format_func=dice_render.chart_label,
            )
            st.radio(
                "Finding / outline",
                [True, False],
                key=f"dice_face_{index}_significant",
                format_func=dice_render.finding_label,
                horizontal=True,
            )
            st.number_input(
                "Seed",
                min_value=0,
                max_value=9999,
                step=1,
                key=f"dice_face_{index}_seed",
                help="Changes the deterministic geometry while preserving the selected chart type.",
            )

cfg = current_config()
with st.spinner("Reducing the six charts to die-scale contours…"):
    face_specs, face_svgs = dice_render.render_faces(cfg)

st.divider()
st.subheader("Distance check")
st.caption(
    "Previewed as a 3 × 2 set at compact scale. If a face becomes visual noise here, choose a "
    "simpler silhouette or change its seed before export."
)
st.iframe(dice_render.render_preview_html(face_specs, face_svgs), height=590)

zip_bytes = dice_render.build_faces_zip(cfg, face_specs, face_svgs)
st.download_button(
    "📦 Download all six SVG faces",
    zip_bytes,
    "phacker-dice-faces.zip",
    "application/zip",
    width="stretch",
    help="Includes six standalone SVGs plus manifest.json with chart, finding, seed, color, and transparency settings.",
)

with st.expander("Download individual SVG faces"):
    download_columns = st.columns(3)
    for index, (spec, svg) in enumerate(zip(face_specs, face_svgs), start=1):
        with download_columns[(index - 1) % 3]:
            st.download_button(
                f"Face {index} · {dice_render.chart_label(spec['chart'])}",
                svg,
                dice_render.face_filename(index, spec),
                "image/svg+xml",
                key=f"download_dice_face_{index}",
                width="stretch",
            )
