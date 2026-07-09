"""
P-Hacker Card Art Tweaker
=========================
Streamlit app: live-tune every chart-art param, preview the raw matplotlib render
PLUS the real card composite (cream stock + band + faint chart at 0.6 opacity).
Export a YAML config to paste back for canonical baking.
Export a print-ready PDF (A4, 4×4, 41.27×57.79 mm + 3 mm bleed).

Deploy on Streamlit Cloud → push to GitHub → share.streamlit.io → done.
"""

from __future__ import annotations
import contextvars, copy, io, os
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import yaml

# ──────────────────────────────────────────────────────────────────────────────
#  PAGE CONFIG
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="P-Hacker Card Tweaker",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────────────
#  LOAD / INIT CONFIG (session state)
# ──────────────────────────────────────────────────────────────────────────────
DEFAULTS_PATH = Path(globals().get("__file__", "app.py")).parent / "config_defaults.yaml"

def _load_defaults() -> dict:
    if DEFAULTS_PATH.exists():
        with open(DEFAULTS_PATH) as f:
            return yaml.safe_load(f)
    # Fallback if file missing
    return {
        "palette": {"SIG": "#426183", "NULL": "#767676"},
        "cmyk": {"effect": [50, 26, 0, 49], "no_effect": [0, 0, 0, 54]},
        "hatch": {"bar": ["///", "|||"], "box": ["///", "+++"], "gauss": "/"},
        "hatch_lw": 2.2, "dpi": 150, "seeds_per_type": 2, "band_pct": 20,
        "syn": {"periods": 20, "intervention": 10, "placebos": 12, "sigma": 0.23,
                "lw": 1.3, "alpha": 0.15, "effect_lw": 1.8, "sig_sigma": 0.15,
                "null_sigma": 0.23, "toe": 0.1, "div_min": 1.0, "div_max": 1.5},
    }

if "cfg" not in st.session_state:
    st.session_state.cfg = _load_defaults()

cfg = st.session_state.cfg   # alias — mutated by sliders in-place


# ──────────────────────────────────────────────────────────────────────────────
#  COLOUR HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def cmyk_to_hex(C: int, M: int, Y: int, K: int) -> str:
    c, m, y, k = C/100, M/100, Y/100, K/100
    r = int(round((1-c)*(1-k)*255))
    g = int(round((1-m)*(1-k)*255))
    b = int(round((1-y)*(1-k)*255))
    return f"#{r:02x}{g:02x}{b:02x}"

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def hex_to_rgb01(h: str) -> tuple[float, float, float]:
    r, g, b = hex_to_rgb(h)
    return r/255, g/255, b/255


# ──────────────────────────────────────────────────────────────────────────────
#  CHART GENERATORS (self-contained, read from cfg / module-level vars)
# ──────────────────────────────────────────────────────────────────────────────

_dpi_ctx:  contextvars.ContextVar[int]   = contextvars.ContextVar("dpi",  default=150)
_fs_ctx:   contextvars.ContextVar[float] = contextvars.ContextVar("fs",   default=1.0)

@contextmanager
def _render_ctx(dpi: int, fs: float = 1.0):
    t1 = _dpi_ctx.set(dpi); t2 = _fs_ctx.set(fs)
    try: yield
    finally: _dpi_ctx.reset(t1); _fs_ctx.reset(t2)

def _fs(pts: float) -> float:
    return round(pts * _fs_ctx.get(), 2)

# Ink colors — updated before each draw call
_INK  = "#000000"
_DIML = "#8C8C8C"
_GRID = "#C9C2B4"
_BG   = "#FFFFFF"


def _apply_style(hatch_lw: float):
    serif = ["STIXGeneral", "DejaVu Serif", "Bitstream Vera Serif", "serif"]
    plt.rcParams.update({
        "font.family": "serif", "font.serif": serif,
        "mathtext.fontset": "cm", "font.size": 8,
        "axes.labelsize": 8, "axes.titlesize": 8,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.linewidth": 0.9, "axes.edgecolor": _INK,
        "axes.labelcolor": _INK, "xtick.color": _INK, "ytick.color": _INK,
        "grid.linestyle": ":", "grid.linewidth": 0.55, "grid.color": _GRID,
        "grid.alpha": 1.0, "axes.unicode_minus": False,
        "figure.facecolor": _BG, "savefig.facecolor": _BG,
        "xtick.direction": "in", "ytick.direction": "in",
        "xtick.top": True, "ytick.right": True,
        "legend.frameon": True, "legend.fancybox": False,
        "legend.edgecolor": _INK, "legend.facecolor": _BG,
        "hatch.linewidth": hatch_lw,
    })

def _setup_axes(ax, grid_axis="y"):
    ax.set_facecolor(_BG)
    ax.tick_params(labelsize=_fs(7), length=3, width=0.6, colors=_INK)
    for sp in ax.spines.values():
        sp.set_visible(True); sp.set_color(_INK); sp.set_linewidth(0.9)
    ax.grid(axis=grid_axis, color=_GRID, linewidth=0.55, linestyle=":")

def _fig_to_pil(fig) -> Image.Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.05,
                facecolor=_BG, dpi=_dpi_ctx.get())
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGBA")


# ── individual generators ──────────────────────────────────────────────────

def gen_bar(sig: bool, rng: np.random.Generator, hatch: list, **_) -> Image.Image:
    global _INK, _DIML, _GRID
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    _setup_axes(ax)
    if sig:
        vals = [rng.uniform(3, 5), rng.uniform(7, 10)]
        errs = [rng.uniform(0.3, 0.8), rng.uniform(0.3, 0.8)]
    else:
        base = rng.uniform(4, 7)
        vals = [base + rng.uniform(-0.5, 0.5), base + rng.uniform(-0.5, 0.5)]
        errs = [rng.uniform(1.0, 2.5), rng.uniform(1.0, 2.5)]
    bars = ax.bar(["Control", "Tratamiento"], vals, yerr=errs,
                  color=["none","none"], edgecolor=_INK, linewidth=0.75,
                  width=0.52, capsize=3,
                  error_kw={"ecolor": _INK, "elinewidth": 0.65, "capthick": 0.65})
    bars[0].set_hatch(hatch[0]); bars[1].set_hatch(hatch[1])
    ax.set_ylabel(r"$\mathrm{Efecto}$", fontsize=_fs(8))
    return _fig_to_pil(fig)


def gen_scatter(sig: bool, rng: np.random.Generator, **_) -> Image.Image:
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    _setup_axes(ax, "both")
    n = rng.integers(35, 70); x = rng.normal(0, 1, n)
    fc = _INK if sig else _DIML
    y = (rng.uniform(0.6,1.2)*rng.choice([-1,1])*x + rng.normal(0,0.35,n)) if sig else rng.normal(0,1,n)
    ax.scatter(x, y, s=12, facecolors=fc, edgecolors=_INK, linewidths=0.35, alpha=0.9)
    z = np.polyfit(x, y, 1)
    ax.plot(np.sort(x), np.polyval(z, np.sort(x)), color=_INK, linewidth=1.0, linestyle=(0,(4,3)))
    ax.set_xlabel(r"$\mathrm{Variable}\ X$", fontsize=_fs(8))
    ax.set_ylabel(r"$\mathrm{Variable}\ Y$", fontsize=_fs(8))
    return _fig_to_pil(fig)


def gen_scatter2(sig: bool, rng: np.random.Generator, **_) -> Image.Image:
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    _setup_axes(ax, "both")
    n = rng.integers(40, 80); x = rng.uniform(0, 10, n)
    fc = _INK if sig else _DIML
    y = (rng.uniform(0.5,1.5)*rng.choice([-1,1])*(x-5) + rng.normal(0,1.2,n)) if sig else rng.normal(0,2.5,n)
    ax.scatter(x, y, s=12, facecolors=fc, edgecolors=_INK, linewidths=0.35, alpha=0.9)
    z = np.polyfit(x, y, 1); xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, np.polyval(z, xs), color=_INK, linewidth=1.0, linestyle=(0,(4,3)))
    ax.set_xlabel("Exposición", fontsize=_fs(8))
    ax.set_ylabel(r"$\mathrm{Resultado}$", fontsize=_fs(8))
    return _fig_to_pil(fig)


def gen_gaussian(sig: bool, rng: np.random.Generator, gauss_hatch: str, **_) -> Image.Image:
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    _setup_axes(ax, "both")
    x = np.linspace(-5, 8, 300)
    if sig:
        mu_a, mu_b = -2.0, 2.4; sigma = rng.uniform(0.6, 0.85)
    else:
        mu_a = rng.uniform(-1.0, -0.7); mu_b = mu_a + rng.uniform(1.4, 1.9)
        sigma = rng.uniform(1.35, 1.7)
    def gauss(mu, s): return np.exp(-0.5*((x-mu)/s)**2) / (s*np.sqrt(2*np.pi))
    ya, yb = gauss(mu_a, sigma), gauss(mu_b, sigma)
    # Group A: NO fill (clean outline). Group B: sparse hatch.
    ax.fill_between(x, yb, facecolor="none", hatch=gauss_hatch,
                    edgecolor=_INK, linewidth=0.0, interpolate=True)
    ax.plot(x, ya, color=_INK, linewidth=1.0, linestyle="-",   label=r"$\mathrm{Grupo\ A}$")
    ax.plot(x, yb, color=_INK, linewidth=1.0, linestyle=(0,(5,3)), label=r"$\mathrm{Grupo\ B}$")
    ax.legend(fontsize=_fs(7), loc="upper right"); ax.set_yticks([])
    return _fig_to_pil(fig)


def gen_box(sig: bool, rng: np.random.Generator, hatch: list, **_) -> Image.Image:
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    _setup_axes(ax)
    n = rng.integers(30, 80)
    if sig:
        a = rng.normal(3, 0.8, n); b = rng.normal(6.5, 0.8, n)
    else:
        c = rng.uniform(3, 6)
        a = rng.normal(c, 1.5, n); b = rng.normal(c+rng.uniform(-0.3, 0.3), 1.5, n)
    bp = ax.boxplot([a, b], tick_labels=["Control", "Tratamiento"], patch_artist=True,
                    widths=0.42,
                    medianprops={"color":_INK,"linewidth":1.2},
                    whiskerprops={"color":_INK,"linewidth":0.7},
                    capprops={"color":_INK,"linewidth":0.7},
                    flierprops={"marker":"x","markeredgecolor":_INK,"markersize":4,"linestyle":"none"})
    for patch, h in zip(bp["boxes"], hatch):
        patch.set_facecolor("none"); patch.set_edgecolor(_INK)
        patch.set_linewidth(0.75); patch.set_hatch(h)
    return _fig_to_pil(fig)


def gen_gap(sig: bool, rng: np.random.Generator, **_) -> Image.Image:
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    _setup_axes(ax, "both")
    pre = np.arange(-8, 0); post = np.arange(0, 8)
    pv = rng.normal(0, 0.18, len(pre))
    postv = (np.linspace(0.1, rng.uniform(1.4,2.6), len(post))+rng.normal(0,0.12,len(post))) if sig \
            else rng.normal(0, 0.22, len(post))
    ax.axvline(x=0, color=_DIML, linewidth=0.9, linestyle=":")
    ax.axhline(y=0, color=_GRID, linewidth=0.75)
    kw = dict(color=_INK, linewidth=1.25, marker="s", markersize=3.5,
              markerfacecolor="white", markeredgecolor=_INK, markeredgewidth=0.6)
    ax.plot(pre, pv, **kw); ax.plot(post, postv, **kw)
    ax.set_xlabel("Tiempo relativo", fontsize=_fs(8))
    ax.set_ylabel(r"$\mathrm{Efecto}$", fontsize=_fs(8))
    return _fig_to_pil(fig)


def gen_synthetic(sig: bool, rng: np.random.Generator, syn: dict, **_) -> Image.Image:
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    _setup_axes(ax, "both")
    P, iv = int(syn["periods"]), int(syn["intervention"])
    t = np.arange(P)
    for _ in range(int(syn["placebos"])):
        ax.plot(t, rng.normal(0, syn["sigma"], P),
                color="#8C8C8C", linewidth=syn["lw"], linestyle="-", alpha=syn["alpha"])
    if sig:
        effect = rng.normal(0, syn["sig_sigma"], P)
        effect[iv:] -= np.linspace(syn["toe"], rng.uniform(syn["div_min"], syn["div_max"]), P-iv)
    else:
        effect = rng.normal(0, syn["null_sigma"], P)
    ax.plot(t, effect, color=_INK, linewidth=syn["effect_lw"], linestyle="-", zorder=5)
    ax.axvline(x=iv, color=_DIML, linewidth=0.6, linestyle=(0,(4,3)))
    ax.axhline(y=0, color=_GRID, linewidth=0.6)
    ylim = ax.get_ylim()
    ax.text(iv+0.35, ylim[0]+0.12*(ylim[1]-ylim[0]),
            "intervención", fontsize=_fs(7), color=_INK, style="italic")
    ax.set_xticks([]); ax.set_ylabel(r"$\mathrm{Efecto}$", fontsize=_fs(8))
    return _fig_to_pil(fig)


def gen_forest(sig: bool, rng: np.random.Generator, **_) -> Image.Image:
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    n = int(rng.integers(6, 9)); ys = np.arange(n)[::-1]
    centers = rng.uniform(0.45,1.5,n)*rng.choice([-1,1]) if sig else rng.uniform(-0.35,0.35,n)
    err = rng.uniform(0.15, 0.5, n)
    ax.axvline(0, color=_DIML, linewidth=0.9, linestyle=(0,(4,3)))
    for y, cx, e in zip(ys, centers, err):
        ax.plot([cx-e, cx+e], [y, y], color=_INK, linewidth=1.3)
        ax.plot([cx], [y], marker="s", color=_INK, markersize=4.5)
    ax.set_yticks([]); ax.set_xlim(-2.2, 2.2); ax.set_ylim(-0.6, n-0.4)
    return _fig_to_pil(fig)


def gen_did(sig: bool, rng: np.random.Generator, **_) -> Image.Image:
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    t = np.arange(0, 11); k = 5
    slope = rng.uniform(0.12, 0.22); c0 = rng.uniform(0.8, 1.2)
    gap0 = rng.uniform(1.4, 1.9)
    control = c0 + slope*t + rng.normal(0, 0.04, len(t))
    trend = (c0+gap0) + slope*t; treated = trend.copy()
    if sig:
        treated[k:] += np.linspace(0, rng.uniform(1.0,1.7), len(t)-k)
    else:
        treated = treated + rng.normal(0, 0.05, len(t))
    ax.plot(t, control, color=_INK, linewidth=1.4, marker="o",
            markersize=3.0, markerfacecolor="white", markeredgecolor=_INK)
    ax.plot(t, treated, color=_INK, linewidth=1.7, marker="s",
            markersize=3.2, markerfacecolor="white", markeredgecolor=_INK)
    ax.plot(t[k:], trend[k:], color=_DIML, linewidth=1.2, linestyle=(0,(5,3)))
    ax.axvline(k, color=_DIML, linewidth=0.9, linestyle=(0,(4,3)))
    return _fig_to_pil(fig)


def gen_event(sig: bool, rng: np.random.Generator, **_) -> Image.Image:
    fig, ax = plt.subplots(figsize=(2.8, 2.0))
    pre = np.arange(-4, 0); post = np.arange(0, 6)
    periods = np.concatenate([pre, post])
    pre_est = rng.normal(0, 0.06, len(pre))
    if sig:
        d = rng.choice([-1, 1])
        post_est = d*np.linspace(0.25, rng.uniform(1.3,2.0), len(post))+rng.normal(0,0.05,len(post))
        err = np.concatenate([rng.uniform(0.16,0.26,len(pre)), rng.uniform(0.16,0.30,len(post))])
    else:
        post_est = rng.normal(0, 0.10, len(post))
        err = rng.uniform(0.22, 0.40, len(periods))
    est = np.concatenate([pre_est, post_est])
    ax.axhline(0, color=_DIML, linewidth=0.9)
    ax.axvline(-0.5, color=_DIML, linewidth=0.9, linestyle=(0,(4,3)))
    ax.errorbar(periods, est, yerr=err, fmt="o", color=_INK, ecolor=_INK,
                markersize=3.4, markerfacecolor="white", markeredgecolor=_INK,
                elinewidth=1.5, capsize=2.5, capthick=1.2)
    return _fig_to_pil(fig)


# Registry: (name, fn, has_chart_specific_params)
GENERATORS: list[tuple[str, callable]] = [
    ("bar_chart",          gen_bar),
    ("scatter_plot",       gen_scatter),
    ("scatter_plot_2",     gen_scatter2),
    ("gaussian_curves",    gen_gaussian),
    ("box_plot",           gen_box),
    ("gap_chart",          gen_gap),
    ("synthetic_control",  gen_synthetic),
    ("forest_plot",        gen_forest),
    ("did_parallel_trends",gen_did),
    ("event_study",        gen_event),
]


# ──────────────────────────────────────────────────────────────────────────────
#  CARD COMPOSITE RENDER (PIL — cream bg + band + chart at 0.6 opacity)
# ──────────────────────────────────────────────────────────────────────────────
CREAM = (242, 236, 224)
CREAM_EDGE = (217, 207, 185)

def render_card_composite(
    chart_pil: Image.Image,
    ink_hex: str,
    label: str,
    band_pct: int = 20,
    paper: str = "cream",
) -> Image.Image:
    """Render the full card face: paper stock + band + faint chart texture."""
    # Card at 150 DPI → 41.27mm × 57.79mm ≈ 244×342 px
    W = int(41.27 / 25.4 * 150)
    H = int(57.79 / 25.4 * 150)
    R = 14  # corner radius in px

    stock = {"white": (255, 255, 255), "cream": CREAM, "manila": (239, 231, 210)}.get(paper, CREAM)

    # Base card (stock colour)
    card = Image.new("RGBA", (W, H), stock + (255,))

    # Corner vignettes (aged look, digital-only)
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dv = ImageDraw.Draw(vig)
    for corner_x, corner_y in [(0,0),(W,0),(0,H),(W,H)]:
        r = int(W * 0.55)
        dv.ellipse([corner_x-r, corner_y-r, corner_x+r, corner_y+r],
                   fill=(140, 110, 60, 28))
    card = Image.alpha_composite(card, vig)

    draw = ImageDraw.Draw(card)

    # Band (top band_pct % of card height)
    band_h = int(H * band_pct / 100)
    ir, ig, ib = hex_to_rgb(ink_hex)
    draw.rounded_rectangle([0, 0, W, band_h], radius=R, fill=(ir, ig, ib, 255))

    # Band label (knocked out to paper)
    label_text = label.upper()
    font_size = max(10, int(band_h * 0.42))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label_text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    tx = (W - tw) // 2; ty = (band_h - th) // 2
    draw.text((tx, ty), label_text, font=font, fill=stock + (255,))

    # Fold creases (horizontal + vertical)
    draw.line([(0, H//2), (W, H//2)], fill=(160, 130, 80, 25), width=1)
    draw.line([(W//2, band_h), (W//2, H)], fill=(160, 130, 80, 18), width=1)

    # Chart texture (0.6 opacity, below band)
    chart_area_top = band_h + 4
    chart_area_h   = H - chart_area_top - 6
    chart_area_w   = W - 8

    chart_resized = chart_pil.resize((chart_area_w, chart_area_h), Image.LANCZOS).convert("RGBA")
    # Set chart background to transparent, keep ink at 0.6 opacity
    r_ch, g_ch, b_ch, a_ch = chart_resized.split()
    a_ch = a_ch.point(lambda x: int(x * 0.6))
    chart_resized = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))
    card.paste(chart_resized, (4, chart_area_top), chart_resized)

    # Bureau stamp (small rectangle, bottom right, faint)
    sx = int(W * 0.72); sy = int(H * 0.87)
    sw = int(W * 0.22); sh = int(H * 0.06)
    draw.rectangle([sx, sy, sx+sw, sy+sh],
                   outline=(ir, ig, ib, 40), width=1)

    # Rounded card border
    draw.rounded_rectangle([0, 0, W-1, H-1], radius=R,
                            outline=CREAM_EDGE + (180,), width=1)

    return card.convert("RGB")


# ──────────────────────────────────────────────────────────────────────────────
#  DRAW HELPERS (call generator + card composite, return both PIL images)
# ──────────────────────────────────────────────────────────────────────────────
def _set_ink(hex_color: str):
    global _INK, _DIML, _GRID
    _INK = _DIML = hex_color
    _DIML = "#8C8C8C"   # always light-gray dim (not the finding color)
    _GRID = "#C9C2B4"

def draw_pair(
    gen_fn: callable,
    sig: bool,
    seed: int,
    cfg: dict,
    ink_hex: str,
    label: str,
    paper: str = "cream",
) -> tuple[Image.Image, Image.Image]:
    """Return (raw_chart_pil, card_composite_pil)."""
    global _INK, _DIML, _GRID
    _apply_style(cfg["hatch_lw"])
    _set_ink(ink_hex)

    hatch_bar   = cfg["hatch"]["bar"]
    hatch_box   = cfg["hatch"]["box"]
    gauss_hatch = cfg["hatch"]["gauss"]
    syn         = cfg["syn"]

    rng = np.random.default_rng(seed)
    with _render_ctx(cfg["dpi"]):
        raw = gen_fn(sig, rng,
                     hatch=hatch_bar,     # bar uses this
                     gauss_hatch=gauss_hatch,
                     syn=syn)             # synthetic_control uses this

    card = render_card_composite(raw, ink_hex, label,
                                 band_pct=cfg["band_pct"], paper=paper)
    return raw, card


# ──────────────────────────────────────────────────────────────────────────────
#  PDF EXPORT (matplotlib PDF backend → print-ready A4)
# ──────────────────────────────────────────────────────────────────────────────
MM = 1 / 25.4   # inches per mm
CW_MM, CH_MM = 41.27, 57.79
BLEED_MM = 3.0
CELL_W = (CW_MM + 2*BLEED_MM) * MM
CELL_H = (CH_MM + 2*BLEED_MM) * MM
PAGE_W, PAGE_H = 210*MM, 297*MM
COLS, ROWS = 4, 4


def _draw_card_on_axes(ax_card, chart_pil, ink_hex, label, band_pct):
    """Draw one card into a matplotlib axes (used for PDF)."""
    r, g, b = hex_to_rgb01(ink_hex)
    band_frac = band_pct / 100

    ax_card.set_xlim(0, 1); ax_card.set_ylim(0, 1); ax_card.axis("off")
    ax_card.set_aspect("auto")

    # Card background (cream)
    ax_card.add_patch(mpatches.FancyBboxPatch(
        (0, 0), 1, 1, boxstyle="round,pad=0.025",
        facecolor=(0.95, 0.93, 0.88), edgecolor=(0.85, 0.81, 0.73), linewidth=0.4))

    # Band
    ax_card.add_patch(mpatches.FancyBboxPatch(
        (0, 1-band_frac), 1, band_frac, boxstyle="round,pad=0.02",
        facecolor=(r, g, b), edgecolor="none"))

    # Band label (knocked out to cream)
    ax_card.text(0.5, 1 - band_frac/2, label.upper(),
                 ha="center", va="center", fontsize=4.5,
                 fontweight="bold", color=(0.95, 0.93, 0.88),
                 fontfamily="serif", transform=ax_card.transAxes)

    # Chart (embedded as image at 0.6 alpha)
    chart_top = 1 - band_frac - 0.04
    chart_h   = chart_top - 0.04
    ax_chart = ax_card.inset_axes([0.04, 0.04, 0.92, chart_h], transform=ax_card.transAxes)
    ax_chart.axis("off")
    ax_chart.imshow(np.asarray(chart_pil), aspect="auto", alpha=0.6)

    # Fold creases
    ax_card.axhline(0.5, color=(0.63, 0.51, 0.31), alpha=0.12, linewidth=0.3)
    ax_card.axvline(0.5, color=(0.63, 0.51, 0.31), alpha=0.08, linewidth=0.3)

    # Bureau stamp
    ax_card.add_patch(mpatches.FancyBboxPatch(
        (0.72, 0.04), 0.22, 0.06, boxstyle="round,pad=0.01",
        facecolor="none", edgecolor=(r, g, b), alpha=0.18, linewidth=0.4))


def build_pdf(cfg: dict, paper: str = "cream") -> bytes:
    """Generate a print-ready PDF with EFFECT + NO EFFECT pages."""
    global _INK, _DIML, _GRID
    _apply_style(cfg["hatch_lw"])

    # Pre-render chart images for each generator × 2 seeds
    def render_pool(sig: bool, ink_hex: str, label_str: str) -> list[Image.Image]:
        _set_ink(ink_hex)
        pool = []
        for ti, (_, gen_fn) in enumerate(GENERATORS):
            for s in range(cfg["seeds_per_type"]):
                rng = np.random.default_rng(1000*ti + s*7 + (0 if sig else 500))
                with _render_ctx(cfg["dpi"]):
                    img = gen_fn(sig, rng,
                                 hatch=cfg["hatch"]["bar"],
                                 gauss_hatch=cfg["hatch"]["gauss"],
                                 syn=cfg["syn"])
                pool.append(img)
        return pool

    e_cmyk = cfg["cmyk"]["effect"];   n_cmyk = cfg["cmyk"]["no_effect"]
    e_hex  = cmyk_to_hex(*e_cmyk);   n_hex  = cmyk_to_hex(*n_cmyk)
    paper_c = {"white": (1,1,1), "cream": (0.95,0.93,0.88), "manila": (0.94,0.91,0.82)}.get(paper, (0.95,0.93,0.88))

    sig_pool = render_pool(True,  e_hex, "EFFECT")
    nul_pool = render_pool(False, n_hex, "NO EFFECT")

    band_pct = cfg["band_pct"]
    buf = io.BytesIO()

    with PdfPages(buf) as pdf:
        for pool, ink_hex, label in [(sig_pool, e_hex, "EFFECT"),
                                     (nul_pool, n_hex, "NO EFFECT")]:
            fig = plt.figure(figsize=(PAGE_W, PAGE_H))
            fig.patch.set_facecolor(paper_c)

            off_x = (PAGE_W - COLS * CELL_W) / 2
            off_y = (PAGE_H - ROWS * CELL_H) / 2

            for row in range(ROWS):
                for col in range(COLS):
                    idx = (row * COLS + col) % len(pool)
                    chart_img = pool[idx]

                    # axes in figure-fraction coords
                    x0 = (off_x + col * CELL_W + BLEED_MM*MM) / PAGE_W
                    y0 = 1.0 - (off_y + (row+1) * CELL_H - BLEED_MM*MM) / PAGE_H
                    w  = (CW_MM * MM) / PAGE_W
                    h  = (CH_MM * MM) / PAGE_H

                    ax = fig.add_axes([x0, y0, w, h])
                    _draw_card_on_axes(ax, chart_img, ink_hex, label, band_pct)

                    # Bleed crop mark (optional thin dashed line)
                    # (not drawn to keep it clean for offset printing)

            pdf.savefig(fig, bbox_inches="tight", pad_inches=0, dpi=300)
            plt.close(fig)

    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
#  HATCH OPTIONS (for selectbox)
# ──────────────────────────────────────────────────────────────────────────────
HATCH_OPTS = ["///", "\\\\\\", "|||", "---", "+++", "xxx", "ooo", "...", "/", "\\", "|", "-"]


# ──────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ──────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🃏 P-Hacker Card Tweaker")
    st.caption("Tune → export YAML → paste back to bake canonical SVGs.")

    # ── YAML import ──
    uploaded = st.file_uploader("Import config YAML", type=["yaml","yml"], key="yaml_up")
    if uploaded:
        loaded = yaml.safe_load(uploaded.read())
        st.session_state.cfg = loaded
        cfg = st.session_state.cfg
        st.success("Config loaded ✓")

    st.divider()

    # ── Global params ──
    st.subheader("Global")
    cfg["dpi"]      = st.slider("DPI (preview quality)", 80, 220, cfg["dpi"], 10, key="g_dpi")
    cfg["hatch_lw"] = st.slider("Hatch line weight", 0.5, 5.0, float(cfg["hatch_lw"]), 0.1, key="g_hlw")
    cfg["band_pct"] = st.slider("Band height %", 14, 30, int(cfg["band_pct"]), 1, key="g_band")
    cfg["seeds_per_type"] = st.slider("Seeds per chart type", 1, 5, int(cfg["seeds_per_type"]), 1, key="g_seeds")
    paper = st.selectbox("Paper stock", ["cream", "white", "manila"], key="g_paper")

    st.divider()
    st.subheader("Hatch fills")
    c1, c2 = st.columns(2)
    with c1:
        cfg["hatch"]["bar"][0]  = st.selectbox("Bar control",   HATCH_OPTS, HATCH_OPTS.index(cfg["hatch"]["bar"][0]),  key="h_barc")
        cfg["hatch"]["box"][0]  = st.selectbox("Box control",   HATCH_OPTS, HATCH_OPTS.index(cfg["hatch"]["box"][0]),  key="h_boxc")
    with c2:
        cfg["hatch"]["bar"][1]  = st.selectbox("Bar treatment", HATCH_OPTS, HATCH_OPTS.index(cfg["hatch"]["bar"][1]),  key="h_bart")
        cfg["hatch"]["box"][1]  = st.selectbox("Box treatment", HATCH_OPTS, HATCH_OPTS.index(cfg["hatch"]["box"][1]),  key="h_boxt")
    gauss_opts = ["/", "\\", "//", "\\\\", "|||", "---", "+++", "xxx"]
    gi = gauss_opts.index(cfg["hatch"]["gauss"]) if cfg["hatch"]["gauss"] in gauss_opts else 0
    cfg["hatch"]["gauss"] = st.selectbox("Gaussian Group B hatch", gauss_opts, gi, key="h_gauss")

    st.divider()
    st.subheader("EFFECT ink (blue)")
    e = cfg["cmyk"]["effect"]
    e[0] = st.slider("C", 0, 100, e[0], key="e_c")
    e[1] = st.slider("M", 0, 100, e[1], key="e_m")
    e[2] = st.slider("Y", 0, 100, e[2], key="e_y")
    e[3] = st.slider("K", 0, 100, e[3], key="e_k")
    e_hex = cmyk_to_hex(*e)
    st.markdown(f'<div style="background:{e_hex};border-radius:4px;padding:4px 8px;'
                f'font-family:monospace;font-size:12px;color:#fff">{e_hex}</div>',
                unsafe_allow_html=True)

    st.subheader("NO EFFECT ink (gray)")
    n = cfg["cmyk"]["no_effect"]
    n[0] = st.slider("C", 0, 100, n[0], key="n_c")
    n[1] = st.slider("M", 0, 100, n[1], key="n_m")
    n[2] = st.slider("Y", 0, 100, n[2], key="n_y")
    n[3] = st.slider("K", 0, 100, n[3], key="n_k")
    n_hex = cmyk_to_hex(*n)
    st.markdown(f'<div style="background:{n_hex};border-radius:4px;padding:4px 8px;'
                f'font-family:monospace;font-size:12px;color:#fff">{n_hex}</div>',
                unsafe_allow_html=True)

    st.divider()
    # ── YAML export ──
    yaml_out = yaml.dump(cfg, default_flow_style=False, allow_unicode=True, sort_keys=False)
    st.download_button("📥 Export YAML", yaml_out, "phacker_config.yaml", "text/yaml", use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN AREA — tabs
# ──────────────────────────────────────────────────────────────────────────────
TAB_NAMES = ["🗂 All Charts", "Bar", "Scatter", "Scatter 2", "Gaussian", "Box",
             "Gap", "Synth. Control", "Forest", "DiD", "Event Study",
             "📄 Export PDF"]
tabs = st.tabs(TAB_NAMES)

# Recompute ink hex from sidebar (may have changed)
e_hex = cmyk_to_hex(*cfg["cmyk"]["effect"])
n_hex = cmyk_to_hex(*cfg["cmyk"]["no_effect"])
seed0 = 0   # default seed for previews


# ── helper: render one row (EFFECT + NO EFFECT, raw + card) ──────────────────
def chart_row(tab, gen_name: str, gen_fn: callable, seed: int = 0):
    with tab:
        raw_e, card_e = draw_pair(gen_fn, True,  seed, cfg, e_hex, "EFFECT",    paper)
        raw_n, card_n = draw_pair(gen_fn, False, seed, cfg, n_hex, "NO EFFECT", paper)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.caption(f"**EFFECT** — raw matplotlib")
            st.image(raw_e, use_container_width=True)
        with c2:
            st.caption(f"**EFFECT** — card composite")
            st.image(card_e, use_container_width=True)
        with c3:
            st.caption(f"**NO EFFECT** — raw matplotlib")
            st.image(raw_n, use_container_width=True)
        with c4:
            st.caption(f"**NO EFFECT** — card composite")
            st.image(card_n, use_container_width=True)


# ── Tab 0: All Charts ─────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("All chart types — EFFECT and NO EFFECT")
    st.caption("Quick scan of all 10 types. Use individual tabs to tune params per chart.")
    cols_all = st.columns(5)
    for i, (name, gen_fn) in enumerate(GENERATORS):
        raw_e, card_e = draw_pair(gen_fn, True,  seed0, cfg, e_hex, "EFFECT", paper)
        raw_n, card_n = draw_pair(gen_fn, False, seed0, cfg, n_hex, "NO EFFECT", paper)
        col = cols_all[i % 5]
        with col:
            st.caption(f"**{name}**")
            st.image(card_e, use_container_width=True)
            st.image(card_n, use_container_width=True)


# ── Tabs 1-10: per chart type ─────────────────────────────────────────────────
def make_chart_tab(tab_idx: int, gen_name: str, gen_fn: callable):
    with tabs[tab_idx]:
        st.subheader(gen_name)
        sc, sv = st.columns([1, 3])
        with sc:
            st.caption("Chart seed")
            seed = st.number_input("Seed", 0, 9999, seed0, 1, key=f"seed_{gen_name}")

            if gen_name == "synthetic_control":
                st.caption("Cloud params")
                syn = cfg["syn"]
                syn["placebos"]  = st.slider("Placebos",  4, 30, int(syn["placebos"]),  key=f"syn_p_{gen_name}")
                syn["sigma"]     = st.slider("σ cloud",   0.05, 0.8, float(syn["sigma"]), 0.01, key=f"syn_s_{gen_name}")
                syn["alpha"]     = st.slider("α cloud",   0.05, 0.5, float(syn["alpha"]), 0.01, key=f"syn_a_{gen_name}")
                syn["lw"]        = st.slider("lw cloud",  0.5,  2.5, float(syn["lw"]),    0.1,  key=f"syn_lw_{gen_name}")
                syn["effect_lw"] = st.slider("lw effect", 0.5,  4.0, float(syn["effect_lw"]), 0.1, key=f"syn_elw_{gen_name}")
                syn["sig_sigma"] = st.slider("σ effect",  0.05, 0.5, float(syn["sig_sigma"]),  0.01, key=f"syn_ss_{gen_name}")
                st.caption("Intervention timing")
                syn["intervention"] = st.slider("Intervention at t=", 5, 18, int(syn["intervention"]), key=f"syn_iv_{gen_name}")

        with sv:
            row_c1, row_c2, row_c3, row_c4 = st.columns(4)
            raw_e, card_e = draw_pair(gen_fn, True,  int(seed), cfg, e_hex, "EFFECT",    paper)
            raw_n, card_n = draw_pair(gen_fn, False, int(seed), cfg, n_hex, "NO EFFECT", paper)
            with row_c1:
                st.caption("EFFECT — raw")
                st.image(raw_e, use_container_width=True)
            with row_c2:
                st.caption("EFFECT — card")
                st.image(card_e, use_container_width=True)
            with row_c3:
                st.caption("NO EFFECT — raw")
                st.image(raw_n, use_container_width=True)
            with row_c4:
                st.caption("NO EFFECT — card")
                st.image(card_n, use_container_width=True)

        # Seed sweep — show multiple variants
        with st.expander("📐 Seed sweep (see all variants)"):
            seed_cols = st.columns(cfg["seeds_per_type"] * 2)
            for s in range(cfg["seeds_per_type"]):
                raws_e, cardd_e = draw_pair(gen_fn, True,  s, cfg, e_hex, "EFFECT",    paper)
                raws_n, cardd_n = draw_pair(gen_fn, False, s, cfg, n_hex, "NO EFFECT", paper)
                with seed_cols[s*2]:
                    st.caption(f"EFFECT seed {s}"); st.image(cardd_e, use_container_width=True)
                with seed_cols[s*2+1]:
                    st.caption(f"NO EFFECT seed {s}"); st.image(cardd_n, use_container_width=True)


for ti, (name, fn) in enumerate(GENERATORS):
    make_chart_tab(ti + 1, name, fn)


# ── Tab 11: Export PDF ────────────────────────────────────────────────────────
with tabs[11]:
    st.subheader("Export print-ready PDF")
    st.caption(
        "A4 portrait · 4×4 grid · 41.27×57.79 mm + 3 mm bleed · "
        "Page 1: EFFECT · Page 2: NO EFFECT. "
        "Open in Acrobat or Preview and print at 100% scale (no scaling, no margins)."
    )

    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.markdown(f"""
| Setting | Value |
|---|---|
| EFFECT ink | `{e_hex}` (C{cfg['cmyk']['effect'][0]} M{cfg['cmyk']['effect'][1]} Y{cfg['cmyk']['effect'][2]} K{cfg['cmyk']['effect'][3]}) |
| NO EFFECT ink | `{n_hex}` (C{cfg['cmyk']['no_effect'][0]} M{cfg['cmyk']['no_effect'][1]} Y{cfg['cmyk']['no_effect'][2]} K{cfg['cmyk']['no_effect'][3]}) |
| Paper stock | {paper} |
| Band height | {cfg['band_pct']}% |
| Seeds/type | {cfg['seeds_per_type']} → {len(GENERATORS)*cfg['seeds_per_type']} distinct faces |
""")

    with col_btn:
        if st.button("🖶 Generate PDF", type="primary", use_container_width=True):
            with st.spinner("Rendering all cards…"):
                pdf_bytes = build_pdf(cfg, paper)
            st.download_button(
                "📥 Download PDF",
                pdf_bytes,
                "phacker-print-cards.pdf",
                "application/pdf",
                use_container_width=True,
            )
            st.success(f"PDF ready — {len(pdf_bytes)//1024} KB")

    st.divider()
    st.subheader("Current YAML config")
    st.caption("Copy this and paste it back to the baking pipeline or to me to commit canonical values.")
    st.code(yaml.dump(cfg, default_flow_style=False, allow_unicode=True, sort_keys=False),
            language="yaml")
