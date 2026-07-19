"""Card SVG — export complete card fronts as standalone SVG files."""
from __future__ import annotations

import streamlit as st

from lib import card_svg
from lib import chart_generators as cg
from lib.editor_state import current_config

st.title("🖼️ Card SVG")
st.caption(
    "Export complete card fronts, not just chart glyphs. Every SVG contains a visible paper border "
    "and infill, while the chart state is recorded as the boolean `difference` field. Use the "
    "negative-space checkbox to fill around each chart and redraw its graphic in paper color."
)

chart_names = cg.all_chart_names()

with st.sidebar:
    st.subheader("Card SVG export")
    size = st.selectbox(
        "Card size",
        ["print", "hand", "verdict"],
        format_func=lambda value: {
            "print": "Print card · 41.27 × 57.79 mm",
            "hand": "Hand card · 234 × 327 px",
            "verdict": "Verdict card · 140 × 190 px",
        }[value],
        key="card_svg_size",
    )
    seed = st.number_input(
        "Seed",
        min_value=0,
        max_value=9999,
        step=1,
        key="card_svg_seed",
        help="The same seed is used for every selected chart, so the export is deterministic.",
    )
    include_difference = st.checkbox(
        "Include DIFFERENCE cards",
        value=True,
        key="card_svg_include_difference",
        help="Exports cards with difference=true and the blue finding ink.",
    )
    include_no_difference = st.checkbox(
        "Include NO DIFFERENCE cards",
        value=True,
        key="card_svg_include_no_difference",
        help="Exports cards with difference=false and the gray finding ink.",
    )
    negative_space = st.checkbox(
        "Fill around graphics (negative space)",
        value=False,
        key="card_svg_negative_space",
        help=(
            "Fills the chart area with the finding ink and redraws the chart in paper color, "
            "so the graphic reads as negative space inside the card."
        ),
    )

    selected_charts = st.multiselect(
        "Charts",
        chart_names,
        default=chart_names,
        format_func=card_svg.chart_label,
        key="card_svg_charts",
        help="Each selected chart exports one card per enabled difference state.",
    )

if not selected_charts:
    st.warning("Select at least one chart to render Card SVGs.")
    st.stop()

differences = [
    difference
    for difference, enabled in (
        (True, include_difference),
        (False, include_no_difference),
    )
    if enabled
]
if not differences:
    st.warning("Enable DIFFERENCE, NO DIFFERENCE, or both before exporting.")
    st.stop()

cfg = current_config()
specs = card_svg.card_specs(
    selected_charts,
    int(seed),
    differences,
    negative_space=negative_space,
)
with st.spinner("Rendering standalone card SVGs…"):
    svgs = [
        card_svg.render_card_svg(
            str(spec["chart"]),
            bool(spec["difference"]),
            int(spec["seed"]),
            cfg,
            size=size,
            card_id=f"{index:02d}-{spec['chart']}",
            negative_space=bool(spec["negative_space"]),
        )
        for index, spec in enumerate(specs, start=1)
    ]

st.subheader(f"{len(svgs)} standalone card SVGs")
st.info(
    "Every export includes a paper infill and visible border. The manifest and SVG metadata use "
    "difference=true/false. Negative-space exports fill around the chart and redraw its graphic in paper color."
)
st.iframe(card_svg.render_preview_html(specs, svgs), height=820)

zip_bytes = card_svg.build_cards_zip(specs, svgs, size=size)
st.download_button(
    "📦 Download Card SVG ZIP",
    zip_bytes,
    f"phacker-card-svgs-{size}.zip",
    "application/zip",
    width="stretch",
    help="Includes every selected card SVG plus manifest.json with chart, seed, boolean difference, and negative_space fields.",
)

with st.expander("Download individual Card SVGs"):
    download_columns = st.columns(3)
    for index, (spec, svg) in enumerate(zip(specs, svgs), start=1):
        with download_columns[(index - 1) % 3]:
            st.download_button(
                f"{index:02d} · {card_svg.chart_label(str(spec['chart']))} · "
                f"{card_svg.difference_label(bool(spec['difference']))}",
                svg,
                card_svg.card_filename(index, spec),
                "image/svg+xml",
                key=f"download_card_svg_{index}",
                width="stretch",
            )
