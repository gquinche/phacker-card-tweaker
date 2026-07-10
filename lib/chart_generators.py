"""Chart-art generators — the single source of truth for P-Hacker's evidence-card
"science texture" charts.

This is a from-parity port of tools/card-art/fake_charts_cardart.py in the
phacker-game repo, reconciled with the hatch-only-fill decision (2026-07-09):
fills use matplotlib `hatch=` patterns with `facecolor="none"`, never a flat
alpha wash, so the printed card doesn't flood ink. bar_chart / box_plot /
gaussian_curves are the only chart types with area fills; everything else
(scatter, gap, forest, synthetic_control, km_curve, did_parallel_trends,
event_study) is lines/markers only, so hatching doesn't apply to them.

Chart type coverage note: km_curve (Kaplan-Meier survival) exists in the
real phacker-game generator but had been dropped from this tweaker's earlier
copy — restored here for full parity (11 chart types total).

Each generator has the signature:
    fn(significant: bool, rng: np.random.Generator, cfg: dict, ink_hex: str) -> matplotlib.figure.Figure

`cfg` is the loaded YAML config (see config_defaults.yaml) — hatch choices,
the synthetic_control cloud params, etc. all come from there so the whole
pool can be re-tuned without touching this file.

Output: callers get a live matplotlib Figure and decide the export format
(SVG for true-fidelity card/print rendering, PNG for cheap gallery thumbnails)
via render_svg() / render_png() below — the figure itself is only built once.

Chart-type coverage note (corrected against tools/card-art on
experiment/simplified-ui, 2026-07-09 — trunk is stale): 10 chart types, NOT
11. km_curve (Kaplan-Meier) was deliberately DROPPED — "reads as
medical-specific, not general science texture" — do not reintroduce it.

Color rule for gap_chart and synthetic_control specifically: always draw the
primary line/effect in the finding ink color, even when significant=False.
Other chart types (scatter, box, bar) already keep at least one element
(edgecolor) in the finding hex regardless of significance. This is not a
stylistic choice — the game's own bake pipeline runs an automated "colour
parity test" that scans each stored SVG for the expected finding hex and
fails the bake if a null-finding chart has zero pixels of that hex (all
lines/fills dimmed to gray). Dimming the WHOLE chart for null findings would
silently break that check.
"""

from __future__ import annotations

import io
from contextlib import contextmanager

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

# ── style constants (not finding-dependent) ─────────────────────────────────
DIM_GRAY = "#8C8C8C"      # secondary/dim ink — never the finding color itself
GRID_WARM = "#C9C2B4"     # aged-paper grid tone (warmer than a neutral gray)
BG_WHITE = "#FFFFFF"

FIGSIZE = (2.8, 2.0)


def apply_style(hatch_lw: float) -> None:
    """Set the global matplotlib rcParams for the "printed paper, dvips-era
    LaTeX figure" look. Call once before rendering a batch."""
    serif = ["STIXGeneral", "DejaVu Serif", "Bitstream Vera Serif", "serif"]
    plt.rcParams.update({
        "font.family": "serif", "font.serif": serif,
        "mathtext.fontset": "cm", "font.size": 8,
        "axes.labelsize": 8, "axes.titlesize": 8,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.linewidth": 0.9, "axes.edgecolor": "#000000",
        "axes.labelcolor": "#000000", "xtick.color": "#000000", "ytick.color": "#000000",
        "grid.linestyle": ":", "grid.linewidth": 0.55, "grid.color": GRID_WARM,
        "grid.alpha": 1.0, "axes.unicode_minus": False,
        "figure.facecolor": BG_WHITE, "savefig.facecolor": BG_WHITE,
        "xtick.direction": "in", "ytick.direction": "in",
        "xtick.top": True, "ytick.right": True,
        "legend.frameon": True, "legend.fancybox": False,
        "legend.edgecolor": "#000000", "legend.facecolor": BG_WHITE,
        "hatch.linewidth": hatch_lw,
    })


def _setup_axes(ax, ink_hex: str, grid_axis: str = "y") -> None:
    ax.set_facecolor(BG_WHITE)
    ax.tick_params(labelsize=7, length=3, width=0.6, colors=ink_hex)
    for sp in ax.spines.values():
        sp.set_visible(True)
        sp.set_color(ink_hex)
        sp.set_linewidth(0.9)
    ax.grid(axis=grid_axis, color=GRID_WARM, linewidth=0.55, linestyle=":")


# ── individual chart generators ─────────────────────────────────────────────

def gen_bar_chart(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink)
    hatch = cfg["hatch"]["bar"]
    if sig:
        vals = [rng.uniform(3, 5), rng.uniform(7, 10)]
        errs = [rng.uniform(0.3, 0.8), rng.uniform(0.3, 0.8)]
    else:
        base = rng.uniform(4, 7)
        vals = [base + rng.uniform(-0.5, 0.5), base + rng.uniform(-0.5, 0.5)]
        errs = [rng.uniform(1.0, 2.5), rng.uniform(1.0, 2.5)]
    bars = ax.bar(["Control", "Tratamiento"], vals, yerr=errs,
                   color=["none", "none"], edgecolor=ink, linewidth=0.75,
                   width=0.52, capsize=3,
                   error_kw={"ecolor": ink, "elinewidth": 0.65, "capthick": 0.65})
    bars[0].set_hatch(hatch[0])
    bars[1].set_hatch(hatch[1])
    ax.set_ylabel(r"$\mathrm{Efecto}$", fontsize=8)
    return fig


def gen_scatter_plot(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    n = rng.integers(35, 70)
    x = rng.normal(0, 1, n)
    fc = ink if sig else DIM_GRAY
    y = (rng.uniform(0.6, 1.2) * rng.choice([-1, 1]) * x + rng.normal(0, 0.35, n)) if sig \
        else rng.normal(0, 1, n)
    ax.scatter(x, y, s=12, facecolors=fc, edgecolors=ink, linewidths=0.35, alpha=0.9)
    z = np.polyfit(x, y, 1)
    ax.plot(np.sort(x), np.polyval(z, np.sort(x)), color=ink, linewidth=1.0, linestyle=(0, (4, 3)))
    ax.set_xlabel(r"$\mathrm{Variable}\ X$", fontsize=8)
    ax.set_ylabel(r"$\mathrm{Variable}\ Y$", fontsize=8)
    return fig


def gen_scatter_plot_2(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    n = rng.integers(40, 80)
    x = rng.uniform(0, 10, n)
    fc = ink if sig else DIM_GRAY
    y = (rng.uniform(0.5, 1.5) * rng.choice([-1, 1]) * (x - 5) + rng.normal(0, 1.2, n)) if sig \
        else rng.normal(0, 2.5, n)
    ax.scatter(x, y, s=12, facecolors=fc, edgecolors=ink, linewidths=0.35, alpha=0.9)
    z = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, np.polyval(z, xs), color=ink, linewidth=1.0, linestyle=(0, (4, 3)))
    ax.set_xlabel("Exposición", fontsize=8)
    ax.set_ylabel(r"$\mathrm{Resultado}$", fontsize=8)
    return fig


def gen_gaussian_curves(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    gauss_hatch = cfg["hatch"]["gauss"]
    x = np.linspace(-5, 8, 300)
    if sig:
        mu_a, mu_b = -2.0, 2.4
        sigma = rng.uniform(0.6, 0.85)
    else:
        mu_a = rng.uniform(-1.0, -0.7)
        mu_b = mu_a + rng.uniform(1.4, 1.9)
        sigma = rng.uniform(1.35, 1.7)

    def gauss(mu, s):
        return np.exp(-0.5 * ((x - mu) / s) ** 2) / (s * np.sqrt(2 * np.pi))

    ya, yb = gauss(mu_a, sigma), gauss(mu_b, sigma)
    # Group A stays clean (no fill) — Group B gets a VERY sparse hatch only,
    # so the two-bell overlap silhouette still reads clearly (Alejandro,
    # 2026-07-09: don't let hatching damage the overlap look).
    ax.fill_between(x, yb, facecolor="none", hatch=gauss_hatch, edgecolor=ink,
                     linewidth=0.0, interpolate=True)
    ax.plot(x, ya, color=ink, linewidth=1.0, linestyle="-", label=r"$\mathrm{Grupo\ A}$")
    ax.plot(x, yb, color=ink, linewidth=1.0, linestyle=(0, (5, 3)), label=r"$\mathrm{Grupo\ B}$")
    ax.legend(fontsize=7, loc="upper right")
    ax.set_yticks([])
    return fig


def gen_box_plot(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink)
    hatch = cfg["hatch"]["box"]
    n = rng.integers(30, 80)
    if sig:
        a = rng.normal(3, 0.8, n)
        b = rng.normal(6.5, 0.8, n)
    else:
        c = rng.uniform(3, 6)
        a = rng.normal(c, 1.5, n)
        b = rng.normal(c + rng.uniform(-0.3, 0.3), 1.5, n)
    bp = ax.boxplot([a, b], tick_labels=["Control", "Tratamiento"], patch_artist=True,
                     widths=0.42,
                     medianprops={"color": ink, "linewidth": 1.2},
                     whiskerprops={"color": ink, "linewidth": 0.7},
                     capprops={"color": ink, "linewidth": 0.7},
                     flierprops={"marker": "x", "markeredgecolor": ink, "markersize": 4, "linestyle": "none"})
    for patch, h in zip(bp["boxes"], hatch):
        patch.set_facecolor("none")
        patch.set_edgecolor(ink)
        patch.set_linewidth(0.75)
        patch.set_hatch(h)
    return fig


def gen_gap_chart(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    # Always the finding hex (not dimmed for null) — see module docstring:
    # the null/significant distinction here comes from the DATA SHAPE (does
    # the post-period diverge from zero or not), not from color. Keeps the
    # finding hex present in the baked SVG for the color-parity test.
    color = ink
    pre_t = np.arange(-8, 0)
    post_t = np.arange(0, 8)
    pre_vals = rng.normal(0, 0.18, len(pre_t))
    if sig:
        effect_size = rng.uniform(1.4, 2.6)
        post_vals = np.linspace(0.1, effect_size, len(post_t)) + rng.normal(0, 0.12, len(post_t))
    else:
        post_vals = rng.normal(0, 0.22, len(post_t))
    ax.axvline(x=0, color=DIM_GRAY, linewidth=0.9, linestyle=":")
    ax.axhline(y=0, color=GRID_WARM, linewidth=0.75)
    kw = dict(color=color, linewidth=1.25, marker="s", markersize=3.5,
              markerfacecolor="white", markeredgecolor=color, markeredgewidth=0.6)
    ax.plot(pre_t, pre_vals, **kw)
    ax.plot(post_t, post_vals, **kw)
    ax.set_xlabel("Tiempo relativo", fontsize=8)
    ax.set_ylabel(r"$\mathrm{Efecto}$", fontsize=8)
    return fig


def gen_synthetic_control(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    syn = cfg["syn"]
    periods, iv = int(syn["periods"]), int(syn["intervention"])
    t = np.arange(periods)
    for _ in range(int(syn["placebos"])):
        ax.plot(t, rng.normal(0, syn["sigma"], periods),
                color=DIM_GRAY, linewidth=syn["lw"], linestyle="-", alpha=syn["alpha"])
    if sig:
        effect = rng.normal(0, syn["sig_sigma"], periods)
        effect[iv:] -= np.linspace(syn["toe"], rng.uniform(syn["div_min"], syn["div_max"]), periods - iv)
    else:
        effect = rng.normal(0, syn["null_sigma"], periods)
    ax.plot(t, effect, color=ink, linewidth=syn["effect_lw"], linestyle="-", zorder=5)
    ax.axvline(x=iv, color=DIM_GRAY, linewidth=0.6, linestyle=(0, (4, 3)))
    ax.axhline(y=0, color=GRID_WARM, linewidth=0.6)
    ylim = ax.get_ylim()
    ax.text(iv + 0.35, ylim[0] + 0.12 * (ylim[1] - ylim[0]),
            "intervención", fontsize=7, color=ink, style="italic")
    ax.set_xticks([])
    ax.set_ylabel(r"$\mathrm{Efecto}$", fontsize=8)
    return fig


def gen_forest_plot(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    n = int(rng.integers(6, 9))
    ys = np.arange(n)[::-1]
    centers = rng.uniform(0.45, 1.5, n) * rng.choice([-1, 1]) if sig else rng.uniform(-0.35, 0.35, n)
    err = rng.uniform(0.15, 0.5, n)
    ax.axvline(0, color=DIM_GRAY, linewidth=0.9, linestyle=(0, (4, 3)))
    for y, cx, e in zip(ys, centers, err):
        ax.plot([cx - e, cx + e], [y, y], color=ink, linewidth=1.3)
        ax.plot([cx], [y], marker="s", color=ink, markersize=4.5, markeredgecolor=ink)
    ax.set_yticks([])
    ax.set_xlim(-2.2, 2.2)
    ax.set_ylim(-0.6, n - 0.4)
    return fig


def gen_did_parallel_trends(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    t = np.arange(0, 11)
    k = 5
    slope = rng.uniform(0.12, 0.22)          # SAME slope both groups -> parallel pre-trend
    c0 = rng.uniform(0.8, 1.2)
    gap0 = rng.uniform(1.4, 1.9)
    control = c0 + slope * t + rng.normal(0, 0.04, len(t))
    treated_trend = (c0 + gap0) + slope * t
    treated = treated_trend.copy()
    if sig:
        treated[k:] += np.linspace(0, rng.uniform(1.0, 1.7), len(t) - k)
    else:
        treated = treated + rng.normal(0, 0.05, len(t))
    ax.plot(t, control, color=ink, linewidth=1.4, marker="o",
            markersize=3.0, markerfacecolor="white", markeredgecolor=ink)
    ax.plot(t, treated, color=ink, linewidth=1.7, marker="s",
            markersize=3.2, markerfacecolor="white", markeredgecolor=ink)
    ax.plot(t[k:], treated_trend[k:], color=DIM_GRAY, linewidth=1.2, linestyle=(0, (5, 3)))
    ax.axvline(k, color=DIM_GRAY, linewidth=0.9, linestyle=(0, (4, 3)))
    return fig


def gen_event_study(sig, rng, cfg, ink):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    pre = np.arange(-4, 0)
    post = np.arange(0, 6)
    periods = np.concatenate([pre, post])
    pre_est = rng.normal(0, 0.06, len(pre))
    if sig:
        d = rng.choice([-1, 1])
        post_est = d * np.linspace(0.25, rng.uniform(1.3, 2.0), len(post)) + rng.normal(0, 0.05, len(post))
        err = np.concatenate([rng.uniform(0.16, 0.26, len(pre)), rng.uniform(0.16, 0.30, len(post))])
    else:
        post_est = rng.normal(0, 0.10, len(post))
        err = rng.uniform(0.22, 0.40, len(periods))
    est = np.concatenate([pre_est, post_est])
    ax.axhline(0, color=DIM_GRAY, linewidth=0.9)
    ax.axvline(-0.5, color=DIM_GRAY, linewidth=0.9, linestyle=(0, (4, 3)))
    ax.errorbar(periods, est, yerr=err, fmt="o", color=ink, ecolor=ink,
                markersize=3.4, markerfacecolor="white", markeredgecolor=ink,
                elinewidth=1.5, capsize=2.5, capthick=1.2)
    return fig


# name -> generator. Order + membership matches the real game's
# CHART_GENERATORS registry on tools/card-art (experiment/simplified-ui):
# bar, scatter, scatter_2, gaussian, box, gap, synthetic_control, forest,
# did_parallel_trends, event_study. Exactly 10 — km_curve is deliberately
# excluded (see module docstring).
GENERATORS: list[tuple[str, callable]] = [
    ("bar_chart", gen_bar_chart),
    ("scatter_plot", gen_scatter_plot),
    ("scatter_plot_2", gen_scatter_plot_2),
    ("gaussian_curves", gen_gaussian_curves),
    ("box_plot", gen_box_plot),
    ("gap_chart", gen_gap_chart),
    ("synthetic_control", gen_synthetic_control),
    ("forest_plot", gen_forest_plot),
    ("did_parallel_trends", gen_did_parallel_trends),
    ("event_study", gen_event_study),
]
GENERATOR_NAMES = [n for n, _ in GENERATORS]

# Weighted random selection (matches the real repo's _WEIGHTS — scatter
# variants sampled more often). Index order must match GENERATORS above.
GENERATOR_WEIGHTS = [1, 3, 3, 2, 1, 2, 2, 2, 2, 2]


@contextmanager
def _closing(fig):
    try:
        yield fig
    finally:
        plt.close(fig)


def build_figure(name: str, significant: bool, seed: int, cfg: dict, ink_hex: str):
    """Build (but do not close) the matplotlib Figure for one chart. Caller
    is responsible for closing it (render_svg/render_png do this for you)."""
    apply_style(float(cfg["hatch_lw"]))
    fn = dict(GENERATORS)[name]
    rng = np.random.default_rng(seed)
    return fn(significant, rng, cfg, ink_hex)


def render_svg(name: str, significant: bool, seed: int, cfg: dict, ink_hex: str) -> str:
    """Render one chart straight to an SVG string (vector, crisp at any size,
    what both the on-screen real-card preview and the print PDF embed)."""
    fig = build_figure(name, significant, seed, cfg, ink_hex)
    with _closing(fig):
        buf = io.StringIO()
        fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.05,
                    facecolor="white", metadata={"Date": None})
        return buf.getvalue()


def render_png(name: str, significant: bool, seed: int, cfg: dict, ink_hex: str) -> Image.Image:
    """Render one chart to a PIL image — cheap raster thumbnail for gallery
    grids where dropping in ~20 live SVGs (each its own DOM subtree) would be
    unnecessarily heavy."""
    fig = build_figure(name, significant, seed, cfg, ink_hex)
    with _closing(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.05,
                    facecolor="white", dpi=int(cfg["dpi"]))
        buf.seek(0)
        return Image.open(buf).convert("RGBA")


def all_chart_names() -> list[str]:
    return list(GENERATOR_NAMES)
