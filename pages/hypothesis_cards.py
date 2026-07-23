"""Print-ready atlas containing every canonical P-Hacker hypothesis card."""
from __future__ import annotations

from copy import deepcopy

import streamlit as st

from lib.config_io import PAGE_SIZES_MM, dump_yaml
from lib.editor_state import current_config
from lib.hypothesis_cards import (
    hypothesis_source,
    load_hypotheses,
    render_hypothesis_atlas_html,
    select_hypotheses,
)
from lib.ink_control import audit_print_html
from lib.pdf_pipeline import PdfPipelineError, PdfRendererUnavailable, build_pdf_bytes

st.title("🗂️ Hypothesis Cards")
st.caption(
    "Build one print-ready PDF from the full canonical P-Hacker hypothesis catalog. "
    "The default export includes all main-game and Investor Mode claims, in English and Spanish, "
    "with matching neutral card backs."
)

base_cfg = current_config()
base_print = base_cfg["print"]
all_cards = load_hypotheses()
source = hypothesis_source()

pool_options = {
    "Main game · 49 cards": "main",
    "Investor Mode · 17 cards": "investor",
}
language_options = {
    "Bilingual · English + Español": "bilingual",
    "English": "en",
    "Español": "es",
}

with st.sidebar:
    st.subheader("Hypothesis export")
    selected_pool_labels = st.multiselect(
        "Card pools",
        list(pool_options),
        default=list(pool_options),
        key="hypothesis_export_pools",
        help="Leave both selected to print every canonical hypothesis card.",
    )
    language_label = st.selectbox(
        "Card language",
        list(language_options),
        key="hypothesis_export_language",
    )
    include_backs = st.checkbox(
        "Include matching card-back sheets",
        value=bool(base_print.get("include_back_pages", True)),
        key="hypothesis_export_backs",
        help="Adds one back sheet for every front sheet, preserving the same cell order for duplex printing.",
    )
    show_card_ids = st.checkbox(
        "Print stable hypothesis IDs",
        value=bool(base_print.get("show_card_id", True)),
        key="hypothesis_export_ids",
    )

    st.subheader("Sheet geometry")
    page_name = st.selectbox(
        "Page size",
        list(PAGE_SIZES_MM),
        index=list(PAGE_SIZES_MM).index(base_print["page"]),
        format_func=lambda value: value.replace("_", " ").title(),
        key="hypothesis_export_page",
    )
    col1, col2 = st.columns(2)
    with col1:
        cols = st.number_input(
            "Columns",
            1,
            8,
            value=int(base_print["cols"]),
            step=1,
            key="hypothesis_export_cols",
        )
    with col2:
        rows = st.number_input(
            "Rows",
            1,
            8,
            value=int(base_print["rows"]),
            step=1,
            key="hypothesis_export_rows",
        )
    col1, col2 = st.columns(2)
    with col1:
        card_w = st.number_input(
            "Card width (mm)",
            25.0,
            80.0,
            value=float(base_print["card_w_mm"]),
            step=0.01,
            key="hypothesis_export_card_w",
        )
    with col2:
        card_h = st.number_input(
            "Card height (mm)",
            40.0,
            120.0,
            value=float(base_print["card_h_mm"]),
            step=0.01,
            key="hypothesis_export_card_h",
        )
    bleed = st.number_input(
        "Bleed (mm)",
        0.0,
        5.0,
        value=float(base_print["bleed_mm"]),
        step=0.5,
        key="hypothesis_export_bleed",
    )
    round_corners = st.checkbox(
        "Render rounded corners in print",
        value=bool(base_print.get("round_corners", False)),
        key="hypothesis_export_round_corners",
    )
    corner_radius = st.number_input(
        "Corner radius (mm)",
        0.5,
        8.0,
        value=float(base_print.get("corner_radius_mm", 3.0)),
        step=0.5,
        disabled=not round_corners,
        key="hypothesis_export_corner_radius",
    )

    st.subheader("PDF")
    use_cmyk = st.checkbox(
        "Write true CMYK into the PDF",
        value=bool(base_print.get("use_cmyk", True)),
        key="hypothesis_export_cmyk",
    )
    pdf_renderer = st.selectbox(
        "PDF renderer",
        ["auto", "browser", "weasyprint"],
        index=["auto", "browser", "weasyprint"].index(base_print.get("pdf_renderer", "auto")),
        format_func=lambda value: {
            "auto": "Auto (browser first)",
            "browser": "Chromium / Playwright",
            "weasyprint": "WeasyPrint fallback",
        }[value],
        key="hypothesis_export_renderer",
    )
    profile_path = st.text_input(
        "CMYK ICC profile path (optional)",
        value=base_print.get("cmyk_profile_path", ""),
        key="hypothesis_export_profile",
    )

selected_pools = [pool_options[label] for label in selected_pool_labels]
language = language_options[language_label]
cards = select_hypotheses(all_cards, selected_pools)

if not cards:
    st.warning("Select at least one card pool to build the hypothesis atlas.")
    st.stop()

cfg = deepcopy(base_cfg)
cfg["print"].update({
    "page": page_name,
    "cols": int(cols),
    "rows": int(rows),
    "card_w_mm": float(card_w),
    "card_h_mm": float(card_h),
    "bleed_mm": float(bleed),
    "show_card_id": bool(show_card_ids),
    "round_corners": bool(round_corners),
    "corner_radius_mm": float(corner_radius),
    "include_back_pages": bool(include_backs),
    "use_cmyk": bool(use_cmyk),
    "pdf_renderer": pdf_renderer,
    "cmyk_profile_path": profile_path,
})

page_w, page_h = PAGE_SIZES_MM[page_name]
cell_w = float(card_w) + float(bleed) * 2
cell_h = float(card_h) + float(bleed) * 2
capacity = int(cols) * int(rows)
front_sheets = (len(cards) + capacity - 1) // capacity
st.info(
    f"{len(cards)} cards · {front_sheets} front sheet(s)"
    f"{' + ' + str(front_sheets) + ' back sheet(s)' if include_backs else ''} · "
    f"{int(cols)}×{int(rows)} on {page_w:.0f}×{page_h:.0f} mm · "
    f"{cell_w:.2f}×{cell_h:.2f} mm cells"
)

subject_counts: dict[str, int] = {}
for card in cards:
    subject_counts[card.subject] = subject_counts.get(card.subject, 0) + 1
summary_col, source_col = st.columns([2, 3])
with summary_col:
    st.markdown("**Included cards**")
    st.dataframe(
        [{"Subject": subject.replace("tech", " tech").title(), "Cards": count} for subject, count in subject_counts.items()],
        hide_index=True,
        width="stretch",
    )
with source_col:
    st.markdown("**Canonical source**")
    st.code(
        f"{source.repository_path}\n{source.branch}@{source.commit}",
        language="text",
    )
    st.caption(
        "This repository bundles a reviewed snapshot so PDF generation stays deterministic and works without live GitHub access."
    )

try:
    atlas_html = render_hypothesis_atlas_html(
        cfg,
        cards,
        language=language,
        include_backs=include_backs,
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

st.subheader("Paper preview")
st.caption("Every canonical ID appears exactly once on a front sheet; optional backs preserve the same sheet order.")
st.iframe(atlas_html, height="content")

ink_audit = audit_print_html(atlas_html, cfg)
if ink_audit["safe"]:
    st.success("Ink preflight passed: hypothesis fronts and backs stay within the neutral BACK ink policy.")
else:
    st.error(f"Ink preflight found {len(ink_audit['warnings'])} foreign-ink condition(s).")
    for warning in ink_audit["warnings"]:
        st.warning(warning.message)

st.subheader("Generate print-ready file")
current_signature = "\n".join([
    dump_yaml(cfg),
    language,
    ",".join(card.id for card in cards),
    f"include_backs={include_backs}",
])

if st.button("🖶 Generate hypothesis-card PDF", type="primary", width="stretch"):
    if cfg["print"].get("strict_ink_check", True) and not ink_audit["safe"]:
        st.error("PDF blocked: resolve the Ink preflight warnings or disable strict checking on Print Atlas.")
    else:
        try:
            with st.spinner(f"Rendering {len(cards)} hypothesis cards…"):
                pdf_bytes = build_pdf_bytes(
                    atlas_html,
                    renderer=pdf_renderer,
                    use_cmyk=use_cmyk,
                    profile_path=profile_path or None,
                )
                st.session_state["_last_hypothesis_pdf"] = pdf_bytes
                st.session_state["_last_hypothesis_pdf_signature"] = current_signature
            st.success(f"Hypothesis-card PDF ready — {len(pdf_bytes) // 1024} KB")
        except PdfRendererUnavailable as exc:
            st.error(
                f"The selected PDF renderer is unavailable: {exc}. "
                "Choose Auto or WeasyPrint, or install Chromium/Playwright."
            )
        except PdfPipelineError as exc:
            st.error(f"PDF/CMYK processing failed: {exc}")
        except Exception as exc:  # noqa: BLE001 — surface deployment/runtime failures
            st.error(f"Hypothesis-card PDF generation failed: {exc}")

if st.session_state.get("_last_hypothesis_pdf_signature") == current_signature:
    st.download_button(
        "📥 Download all hypothesis cards",
        st.session_state["_last_hypothesis_pdf"],
        "phacker-hypothesis-cards.pdf",
        "application/pdf",
        width="stretch",
    )
elif st.session_state.get("_last_hypothesis_pdf"):
    st.info("Hypothesis-card settings changed. Generate the PDF again before downloading.")
