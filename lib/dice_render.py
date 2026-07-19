"""Minimal, distance-readable SVG faces built from the existing chart family.

The card generator remains the source of chart geometry. This module asks it for
one matplotlib figure, removes chart apparatus and fine detail, then places the
remaining contour inside a rounded die face. No labels, axes, fills, hatches, or
legends are carried into the default exported SVG. An optional negative-space
mode fills around the contour and redraws the contour in the die background color.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from html import escape

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PathCollection, PolyCollection

from . import chart_generators as cg

DICE_FACE_COUNT = 6
DICE_SIZE = 256
DICE_NEUTRAL_OUTLINE = "#2b2b2b"
DICE_DEFAULT_BACKGROUND = "#f7f4ec"
DICE_DEFAULT_NEGATIVE_SPACE = False

# Six distinct, strong silhouettes for the initial ladder-of-credibility
# vocabulary. Each chart already contains its paired visual elements (two
# Gaussians, two boxes, two bars, and so on), so the default die avoids
# spending multiple faces on alternate states of the same chart.
DEFAULT_FACE_SPECS: tuple[dict, ...] = (
    {"chart": "gaussian_curves", "significant": True, "seed": 0},
    {"chart": "box_plot", "significant": False, "seed": 1},
    {"chart": "bar_chart", "significant": True, "seed": 0},
    {"chart": "km_curve", "significant": False, "seed": 1},
    {"chart": "forest_plot", "significant": True, "seed": 0},
    {"chart": "did_parallel_trends", "significant": True, "seed": 0},
)

CHART_LABELS = {
    "bar_chart": "Bar plot",
    "scatter_plot": "Scatter plot",
    "scatter_plot_2": "Scatter plot — wide",
    "gaussian_curves": "Two Gaussians",
    "box_plot": "Box and whisker",
    "gap_chart": "Interrupted trend",
    "synthetic_control": "Synthetic control",
    "forest_plot": "Forest plot",
    "km_curve": "Step curves",
    "did_parallel_trends": "Parallel trends",
    "event_study": "Event study",
}

_SVG_RE = re.compile(r'<svg\b[^>]*\bviewBox="([^"]+)"[^>]*>(.*)</svg>\s*$', re.DOTALL)
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def chart_label(name: str) -> str:
    return CHART_LABELS.get(name, name.replace("_", " ").title())


def finding_label(significant: bool) -> str:
    return "EFFECT / blue" if significant else "NO EFFECT / gray"


def _safe_hex(value: object, fallback: str) -> str:
    text = str(value)
    return text.lower() if _HEX_RE.fullmatch(text) else fallback


def face_specs_from_config(cfg: dict) -> list[dict]:
    """Return exactly six validated face specs, filling partial old configs."""
    raw_faces = cfg.get("dice", {}).get("faces", [])
    if not isinstance(raw_faces, list):
        raw_faces = []
    specs: list[dict] = []
    for index, default in enumerate(DEFAULT_FACE_SPECS):
        raw = raw_faces[index] if index < len(raw_faces) and isinstance(raw_faces[index], dict) else {}
        chart = raw.get("chart", default["chart"])
        if chart not in cg.GENERATOR_NAMES:
            chart = default["chart"]
        significant = raw.get("significant", default["significant"])
        if not isinstance(significant, bool):
            significant = default["significant"]
        try:
            seed = max(0, min(9999, int(raw.get("seed", default["seed"]))))
        except (TypeError, ValueError):
            seed = int(default["seed"])
        specs.append({
            "chart": chart,
            "significant": significant,
            "seed": seed,
        })
    return specs


def _simplify_figure(fig, ink_hex: str) -> None:
    """Reduce a full chart to bold contours that survive at die scale."""
    fig.set_size_inches(2.4, 2.4)
    fig.patch.set_alpha(0)
    fig.subplots_adjust(left=0.03, right=0.97, bottom=0.03, top=0.97)

    for ax in fig.axes:
        ax.set_facecolor("none")
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title("")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        ax.margins(0.06)
        for spine in ax.spines.values():
            spine.set_visible(False)
        legend = ax.get_legend()
        if legend is not None:
            legend.remove()
        for text in list(ax.texts):
            text.remove()

        for line in ax.lines:
            alpha = line.get_alpha()
            # Synthetic-control placebo clouds are useful card texture but turn
            # to noise on a die. Keep only the semantic contour and guides.
            if alpha is not None and alpha < 0.55:
                line.set_visible(False)
                continue
            line.set_color(ink_hex)
            line.set_alpha(1)
            line.set_linewidth(max(2.8, float(line.get_linewidth()) * 1.8))
            line.set_solid_capstyle("round")
            line.set_dash_capstyle("round")
            marker = line.get_marker()
            if marker not in (None, "None", "", " "):
                line.set_markersize(max(5.5, float(line.get_markersize()) * 1.5))
                line.set_markeredgewidth(1.5)
                line.set_markeredgecolor(ink_hex)
                line.set_markerfacecolor("none")

        for collection in ax.collections:
            if isinstance(collection, PolyCollection):
                # Gaussian/bar area fills and hatch polygons are deliberately
                # absent: the die language is contour only.
                collection.set_visible(False)
            elif isinstance(collection, PathCollection):
                sizes = collection.get_sizes()
                if len(sizes):
                    collection.set_sizes([max(34.0, float(size) * 2.2) for size in sizes])
                collection.set_facecolors("none")
                collection.set_edgecolors(ink_hex)
                collection.set_linewidths(1.8)
                collection.set_alpha(1)
            elif isinstance(collection, LineCollection):
                collection.set_color(ink_hex)
                collection.set_linewidth(2.6)
                collection.set_alpha(1)
            else:
                try:
                    collection.set_edgecolor(ink_hex)
                    collection.set_facecolor("none")
                    collection.set_linewidth(2.6)
                    collection.set_alpha(1)
                except (AttributeError, TypeError, ValueError):
                    pass

        for patch in ax.patches:
            patch.set_facecolor("none")
            patch.set_edgecolor(ink_hex)
            patch.set_hatch(None)
            patch.set_linewidth(3.2)
            patch.set_alpha(1)


def _render_glyph_svg(
    chart: str,
    significant: bool,
    seed: int,
    cfg: dict,
    ink_hex: str,
    namespace: str,
) -> str:
    if chart not in cg.GENERATOR_NAMES:
        raise ValueError(f"Unknown chart type: {chart}")

    with plt.rc_context({"svg.hashsalt": f"dice-{namespace}-{chart}-{int(significant)}-{seed}"}):
        fig = cg.build_figure(chart, significant, seed, cfg, ink_hex)
        try:
            _simplify_figure(fig, ink_hex)
            buffer = io.StringIO()
            fig.savefig(
                buffer,
                format="svg",
                bbox_inches="tight",
                pad_inches=0.01,
                facecolor="none",
                transparent=True,
                metadata={"Date": None},
            )
            return buffer.getvalue()
        finally:
            plt.close(fig)


def _embedded_svg(svg_text: str, *, x: int, y: int, size: int) -> str:
    match = _SVG_RE.search(svg_text)
    if match is None:
        raise ValueError("Rendered chart did not contain a usable SVG root")
    view_box, body = match.groups()
    return (
        f'<svg x="{x}" y="{y}" width="{size}" height="{size}" '
        f'viewBox="{escape(view_box, quote=True)}" preserveAspectRatio="xMidYMid meet" '
        f'aria-hidden="true">{body}</svg>'
    )


def render_face_svg(
    chart: str,
    significant: bool,
    seed: int,
    cfg: dict,
    *,
    background_hex: str,
    colored_outlines: bool,
    transparent_background: bool = True,
    negative_space: bool = False,
    namespace: str = "standalone",
) -> str:
    """Render one self-contained 256×256 SVG die face."""
    if not isinstance(negative_space, bool):
        raise TypeError("negative_space must be a boolean")
    background = _safe_hex(background_hex, DICE_DEFAULT_BACKGROUND)
    background_element = (
        ""
        if transparent_background
        else f'  <rect width="{DICE_SIZE}" height="{DICE_SIZE}" fill="{background}"/>\n'
    )
    finding_ink = cfg["palette"]["SIG" if significant else "NULL"]
    ink = _safe_hex(finding_ink, DICE_NEUTRAL_OUTLINE) if colored_outlines else DICE_NEUTRAL_OUTLINE
    chart_ink = background if negative_space else ink
    glyph = _render_glyph_svg(chart, significant, int(seed), cfg, chart_ink, namespace)
    title = escape(f"{chart_label(chart)}, {finding_label(significant)}, seed {seed}")
    if negative_space:
        title = f"Negative-space {title}"
    negative_space_element = (
        f'  <rect id="negative-space-fill" x="5" y="5" width="246" height="246" rx="14" fill="{ink}"/>\n'
        if negative_space
        else ""
    )
    metadata = json.dumps({
        "chart": chart,
        "significant": significant,
        "seed": int(seed),
        "negative_space": negative_space,
    }, separators=(",", ":"))

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{DICE_SIZE}" height="{DICE_SIZE}" viewBox="0 0 {DICE_SIZE} {DICE_SIZE}" '
        f'role="img" aria-label="{title}" data-negative-space="{str(negative_space).lower()}" '
        'data-negative-space-meaning="fill-around-graphic">\n'
        f'  <title>{title}</title>\n'
        f'  <metadata>{metadata}</metadata>\n'
        f'{background_element}'
        f'{negative_space_element}'
        f'  {_embedded_svg(glyph, x=28, y=28, size=200)}\n'
        "</svg>"
    )


def render_faces(cfg: dict) -> tuple[list[dict], list[str]]:
    base_specs = face_specs_from_config(cfg)
    dice_cfg = cfg.get("dice", {})
    background = dice_cfg.get("background", DICE_DEFAULT_BACKGROUND)
    transparent = bool(dice_cfg.get("transparent_background", True))
    colored = bool(dice_cfg.get("colored_outlines", True))
    negative = bool(dice_cfg.get("negative_space", DICE_DEFAULT_NEGATIVE_SPACE))
    specs = [dict(spec, negative_space=negative) for spec in base_specs]
    faces = [
        render_face_svg(
            spec["chart"],
            spec["significant"],
            spec["seed"],
            cfg,
            background_hex=background,
            colored_outlines=colored,
            transparent_background=transparent,
            negative_space=bool(spec["negative_space"]),
            namespace=f"face-{index}",
        )
        for index, spec in enumerate(specs, start=1)
    ]
    return specs, faces


def render_preview_html(specs: list[dict], faces: list[str]) -> str:
    cards = []
    for index, (spec, svg) in enumerate(zip(specs, faces), start=1):
        label = escape(chart_label(spec["chart"]))
        finding = escape(finding_label(spec["significant"]))
        variant = "NEGATIVE SPACE" if bool(spec.get("negative_space", False)) else "STANDARD"
        cards.append(
            f'<figure><div class="face">{svg}</div><figcaption>'
            f'<strong>FACE {index}</strong><span>{label}</span><small>{finding} · {variant}</small>'
            "</figcaption></figure>"
        )
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 18px; background: #f1f1ef; color: #252525; font-family: Inter, Arial, sans-serif; }}
.grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }}
figure {{ margin: 0; min-width: 0; }}
.face {{ width: 100%; aspect-ratio: 1; }}
.face > svg {{ display: block; width: 100%; height: 100%; filter: drop-shadow(0 5px 8px rgba(0,0,0,.13)); }}
figcaption {{
  display: grid; grid-template-columns: auto 1fr; gap: 2px 8px;
  padding: 8px 4px 0; align-items: baseline;
}}
strong {{ font-size: 10px; letter-spacing: .12em; }}
span {{ font-size: 13px; }}
small {{ grid-column: 2; color: #686868; font-size: 11px; }}
@media (max-width: 620px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
</style></head><body><main class="grid">{''.join(cards)}</main></body></html>'''


def face_filename(index: int, spec: dict) -> str:
    finding = "effect" if spec["significant"] else "no-effect"
    chart = spec["chart"].replace("_", "-")
    return f"face-{index}-{chart}-{finding}.svg"


def build_faces_zip(cfg: dict, specs: list[dict], faces: list[str]) -> bytes:
    """Package six standalone SVGs plus a small machine-readable manifest."""
    buffer = io.BytesIO()
    dice_cfg = cfg.get("dice", {})
    manifest = {
        "schema_version": 2,
        "background": _safe_hex(dice_cfg.get("background"), DICE_DEFAULT_BACKGROUND),
        "transparent_background": bool(dice_cfg.get("transparent_background", True)),
        "colored_outlines": bool(dice_cfg.get("colored_outlines", True)),
        "negative_space": any(bool(spec.get("negative_space", False)) for spec in specs),
        "negative_space_field": "negative_space",
        "faces": specs,
    }
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, (spec, svg) in enumerate(zip(specs, faces), start=1):
            archive.writestr(face_filename(index, spec), svg)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    return buffer.getvalue()
