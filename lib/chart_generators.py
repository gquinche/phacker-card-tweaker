"""Chart-art generators — the single source of truth for P-Hacker's evidence-card
"science texture" charts.

This is a from-parity port of tools/card-art/fake_charts_cardart.py in the
phacker-game repo (branch experiment/simplified-ui — trunk is stale for card
art), reconciled with the hatch-only-fill decision (2026-07-09): fills use
matplotlib `hatch=` patterns with `facecolor="none"`, never a flat alpha
wash, so the printed card doesn't flood ink. bar_chart / box_plot /
gaussian_curves are the only chart types with area fills; everything else
(scatter, gap, forest, synthetic_control, km_curve, did_parallel_trends,
event_study) is lines/markers only, so hatching doesn't apply to them.

Every chart's "shape" numbers (sample sizes, effect-size ranges, noise
levels) come from `cfg["chart_params"][chart_name]` (see lib/chart_params.py
for the schema + defaults) rather than being hardcoded — that's what lets
pages/chart_lab.py expose a tuning control for every chart type, not just
synthetic_control's old `syn` dict.

Color rule (corrected 2026-07-10, per Alejandro): the only real constraint
is that a chart's finding-color elements always come from the `ink`
parameter passed in — i.e. whatever's actually configured for that finding
in cfg["palette"] / cfg["cmyk"] — never from a hardcoded gray constant that
would silently ignore a palette change. There is no per-SVG pixel-scanning
requirement; a chart is free to mix that finding ink with a separate fixed
decorative gray (DIM_GRAY, used below for things like a placebo cloud or an
axis guide line that's meant to look muted regardless of finding) — mixing
tones like that is normal and doesn't need to "match" anything. gap_chart
and synthetic_control both draw their primary line in `ink` unconditionally
(for both findings) simply so the null-finding line tracks a NULL palette
change instead of staying frozen on DIM_GRAY.

Chart registry: km_curve (Kaplan-Meier) was dropped upstream in phacker-game
("reads as medical-specific, not general science texture") but is restored
here, fully parameterized, since that's a tuning problem, not a reason to
drop the chart type — see lib/chart_params.py.
"""

from __future__ import annotations

import io
from contextlib import contextmanager

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from .chart_params import CHART_PARAM_SCHEMAS

# ── style constants (not finding-dependent) ─────────────────────────────────
DIM_GRAY = "#8C8C8C"      # fixed decorative gray — never a finding color substitute
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


def _p(cfg: dict, name: str) -> dict:
    """This chart's tunable-params sub-dict, falling back to schema defaults
    for any key missing from an older/partial cfg (mirrors config_io's own
    deep-merge safety net at the per-chart level)."""
    params = cfg.get("chart_params", {}).get(name, {})
    schema = CHART_PARAM_SCHEMAS[name]
    return {k: params.get(k, spec[5]) for k, spec in schema.items()}


# ── individual chart generators ─────────────────────────────────────────────

def gen_bar_chart(sig, rng, cfg, ink):
    p = _p(cfg, "bar_chart")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink)
    hatch = cfg["hatch"]["bar"]
    if sig:
        vals = [rng.uniform(*p["sig_control"]), rng.uniform(*p["sig_treatment"])]
        errs = [rng.uniform(*p["sig_err"]), rng.uniform(*p["sig_err"])]
    else:
        base = rng.uniform(*p["null_base"])
        j = p["null_jitter"]
        vals = [base + rng.uniform(-j, j), base + rng.uniform(-j, j)]
        errs = [rng.uniform(*p["null_err"]), rng.uniform(*p["null_err"])]
    bars = ax.bar(["Control", "Tratamiento"], vals, yerr=errs,
                   color=["none", "none"], edgecolor=ink, linewidth=0.75,
                   width=0.52, capsize=3,
                   error_kw={"ecolor": ink, "elinewidth": 0.65, "capthick": 0.65})
    bars[0].set_hatch(hatch[0])
    bars[1].set_hatch(hatch[1])
    ax.set_ylabel(r"$\mathrm{Efecto}$", fontsize=8)
    return fig


def gen_scatter_plot(sig, rng, cfg, ink):
    p = _p(cfg, "scatter_plot")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    n = rng.integers(p["n"][0], p["n"][1] + 1)
    x = rng.normal(0, 1, n)
    fc = ink if sig else DIM_GRAY
    y = (rng.uniform(*p["sig_slope"]) * rng.choice([-1, 1]) * x + rng.normal(0, p["sig_noise"], n)) if sig \
        else rng.normal(0, p["null_noise"], n)
    ax.scatter(x, y, s=12, facecolors=fc, edgecolors=ink, linewidths=0.35, alpha=0.9)
    z = np.polyfit(x, y, 1)
    ax.plot(np.sort(x), np.polyval(z, np.sort(x)), color=ink, linewidth=1.0, linestyle=(0, (4, 3)))
    ax.set_xlabel(r"$\mathrm{Variable}\ X$", fontsize=8)
    ax.set_ylabel(r"$\mathrm{Variable}\ Y$", fontsize=8)
    return fig


def gen_scatter_plot_2(sig, rng, cfg, ink):
    p = _p(cfg, "scatter_plot_2")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    n = rng.integers(p["n"][0], p["n"][1] + 1)
    x = rng.uniform(0, 10, n)
    fc = ink if sig else DIM_GRAY
    y = (rng.uniform(*p["sig_slope"]) * rng.choice([-1, 1]) * (x - 5) + rng.normal(0, p["sig_noise"], n)) if sig \
        else rng.normal(0, p["null_noise"], n)
    ax.scatter(x, y, s=12, facecolors=fc, edgecolors=ink, linewidths=0.35, alpha=0.9)
    z = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, np.polyval(z, xs), color=ink, linewidth=1.0, linestyle=(0, (4, 3)))
    ax.set_xlabel("Exposición", fontsize=8)
    ax.set_ylabel(r"$\mathrm{Resultado}$", fontsize=8)
    return fig


def gen_gaussian_curves(sig, rng, cfg, ink):
    p = _p(cfg, "gaussian_curves")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    gauss_hatch = cfg["hatch"]["gauss"]
    x = np.linspace(-5, 8, 300)
    if sig:
        mu_a, mu_b = p["sig_mu_a"], p["sig_mu_b"]
        sigma = rng.uniform(*p["sig_sigma"])
    else:
        mu_a = rng.uniform(*p["null_mu_a"])
        mu_b = mu_a + rng.uniform(*p["null_gap"])
        sigma = rng.uniform(*p["null_sigma"])

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
    p = _p(cfg, "box_plot")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink)
    hatch = cfg["hatch"]["box"]
    n = rng.integers(p["n"][0], p["n"][1] + 1)
    if sig:
        a = rng.normal(p["sig_a_center"], p["sig_spread"], n)
        b = rng.normal(p["sig_b_center"], p["sig_spread"], n)
    else:
        center = rng.uniform(*p["null_center"])
        off = p["null_offset"]
        a = rng.normal(center, p["null_spread"], n)
        b = rng.normal(center + rng.uniform(-off, off), p["null_spread"], n)
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
    p = _p(cfg, "gap_chart")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    # Always the actual configured finding ink (blue when significant, the
    # configured NULL tone when not) — never a hardcoded gray constant that
    # would ignore a palette change. See module docstring.
    color = ink
    pre_t = np.arange(-8, 0)
    post_t = np.arange(0, 8)
    pre_vals = rng.normal(0, p["pre_noise"], len(pre_t))
    if sig:
        effect_size = rng.uniform(*p["sig_effect"])
        post_vals = np.linspace(0.1, effect_size, len(post_t)) + rng.normal(0, p["sig_post_noise"], len(post_t))
    else:
        post_vals = rng.normal(0, p["null_post_noise"], len(post_t))
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
    p = _p(cfg, "synthetic_control")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "both")
    periods, iv = int(p["periods"]), int(p["intervention"])
    t = np.arange(periods)
    for _ in range(int(p["placebos"])):
        # Placebo cloud: intentionally a fixed decorative gray regardless of
        # finding — it's noise texture, not something carrying finding
        # semantics, so it doesn't need to track the palette. See module docstring.
        ax.plot(t, rng.normal(0, p["sigma"], periods),
                color=DIM_GRAY, linewidth=p["lw"], linestyle="-", alpha=p["alpha"])
    if sig:
        effect = rng.normal(0, p["sig_sigma"], periods)
        effect[iv:] -= np.linspace(p["toe"], rng.uniform(p["div_min"], p["div_max"]), periods - iv)
    else:
        effect = rng.normal(0, p["null_sigma"], periods)
    # Effect line: always the actual configured finding ink (see gap_chart's
    # comment above — same reasoning).
    ax.plot(t, effect, color=ink, linewidth=p["effect_lw"], linestyle="-", zorder=5)
    ax.axvline(x=iv, color=DIM_GRAY, linewidth=0.6, linestyle=(0, (4, 3)))
    ax.axhline(y=0, color=GRID_WARM, linewidth=0.6)
    ylim = ax.get_ylim()
    ax.text(iv + 0.35, ylim[0] + 0.12 * (ylim[1] - ylim[0]),
            "intervención", fontsize=7, color=ink, style="italic")
    ax.set_xticks([])
    ax.set_ylabel(r"$\mathrm{Efecto}$", fontsize=8)
    return fig


def gen_forest_plot(sig, rng, cfg, ink):
    p = _p(cfg, "forest_plot")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    n = int(rng.integers(p["n"][0], p["n"][1] + 1))
    ys = np.arange(n)[::-1]
    centers = rng.uniform(*p["sig_center"], n) * rng.choice([-1, 1]) if sig else rng.uniform(*p["null_center"], n)
    err = rng.uniform(*p["err"], n)
    ax.axvline(0, color=DIM_GRAY, linewidth=0.9, linestyle=(0, (4, 3)))
    for y, cx, e in zip(ys, centers, err):
        ax.plot([cx - e, cx + e], [y, y], color=ink, linewidth=1.3)
        ax.plot([cx], [y], marker="s", color=ink, markersize=4.5, markeredgecolor=ink)
    ax.set_yticks([])
    ax.set_xlim(-2.2, 2.2)
    ax.set_ylim(-0.6, n - 0.4)
    return fig


def gen_km_curve(sig, rng, cfg, ink):
    """Kaplan-Meier survival curves — two step functions (diverge if
    significant, stay together if null). Restored + fully parameterized
    (t_max, resolution, decline-rate ranges) so it can be dialed into
    something that reads as general science texture rather than a clinical
    survival curve, instead of being dropped outright."""
    p = _p(cfg, "km_curve")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    _setup_axes(ax, ink, "y")
    t = np.linspace(0, p["t_max"], int(p["n_points"]))

    def surv(rate):
        return np.exp(-rate * t)

    if sig:
        a = surv(rng.uniform(*p["sig_rate_a"]))
        b = surv(rng.uniform(*p["sig_rate_b"]))
    else:
        r = rng.uniform(*p["null_rate"])
        a = surv(r)
        b = surv(r * rng.uniform(*p["null_jitter"]))
    ax.step(t, a, where="post", color=ink, linewidth=1.5)
    ax.step(t, b, where="post", color=ink, linewidth=1.5, linestyle=(0, (5, 3)))
    ax.set_ylim(0, 1.03)
    ax.set_yticks([])
    return fig


def gen_did_parallel_trends(sig, rng, cfg, ink):
    p = _p(cfg, "did_parallel_trends")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    t = np.arange(0, 11)
    k = 5
    slope = rng.uniform(*p["slope"])          # SAME slope both groups -> parallel pre-trend
    c0 = rng.uniform(*p["c0"])
    gap0 = rng.uniform(*p["gap0"])
    control = c0 + slope * t + rng.normal(0, 0.04, len(t))
    treated_trend = (c0 + gap0) + slope * t
    treated = treated_trend.copy()
    if sig:
        treated[k:] += np.linspace(0, rng.uniform(*p["sig_divergence"]), len(t) - k)
    else:
        treated = treated + rng.normal(0, p["null_noise"], len(t))
    ax.plot(t, control, color=ink, linewidth=1.4, marker="o",
            markersize=3.0, markerfacecolor="white", markeredgecolor=ink)
    ax.plot(t, treated, color=ink, linewidth=1.7, marker="s",
            markersize=3.2, markerfacecolor="white", markeredgecolor=ink)
    ax.plot(t[k:], treated_trend[k:], color=DIM_GRAY, linewidth=1.2, linestyle=(0, (5, 3)))
    ax.axvline(k, color=DIM_GRAY, linewidth=0.9, linestyle=(0, (4, 3)))
    return fig


def gen_event_study(sig, rng, cfg, ink):
    p = _p(cfg, "event_study")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    pre = np.arange(-4, 0)
    post = np.arange(0, 6)
    periods = np.concatenate([pre, post])
    pre_est = rng.normal(0, p["pre_noise"], len(pre))
    if sig:
        d = rng.choice([-1, 1])
        post_est = d * np.linspace(0.25, rng.uniform(*p["sig_effect"]), len(post)) + rng.normal(0, p["sig_noise"], len(post))
        err = np.concatenate([rng.uniform(*p["sig_err_pre"], len(pre)), rng.uniform(*p["sig_err_post"], len(post))])
    else:
        post_est = rng.normal(0, p["null_noise"], len(post))
        err = rng.uniform(*p["null_err"], len(periods))
    est = np.concatenate([pre_est, post_est])
    ax.axhline(0, color=DIM_GRAY, linewidth=0.9)
    ax.axvline(-0.5, color=DIM_GRAY, linewidth=0.9, linestyle=(0, (4, 3)))
    ax.errorbar(periods, est, yerr=err, fmt="o", color=ink, ecolor=ink,
                markersize=3.4, markerfacecolor="white", markeredgecolor=ink,
                elinewidth=1.5, capsize=2.5, capthick=1.2)
    return fig


# name -> generator. km_curve restored (see module docstring) — 11 chart
# types total.
GENERATORS: list[tuple[str, callable]] = [
    ("bar_chart", gen_bar_chart),
    ("scatter_plot", gen_scatter_plot),
    ("scatter_plot_2", gen_scatter_plot_2),
    ("gaussian_curves", gen_gaussian_curves),
    ("box_plot", gen_box_plot),
    ("gap_chart", gen_gap_chart),
    ("synthetic_control", gen_synthetic_control),
    ("forest_plot", gen_forest_plot),
    ("km_curve", gen_km_curve),
    ("did_parallel_trends", gen_did_parallel_trends),
    ("event_study", gen_event_study),
]
GENERATOR_NAMES = [n for n, _ in GENERATORS]
GENERATOR_WEIGHTS = [1, 3, 3, 2, 1, 2, 2, 2, 2, 2, 2]


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
