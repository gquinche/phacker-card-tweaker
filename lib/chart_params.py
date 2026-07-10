"""Per-chart-type tunable parameter schemas.

Every chart generator in chart_generators.py used to hardcode its "shape"
numbers (sample sizes, effect-size ranges, noise levels) as literals in the
function body — only synthetic_control's cloud params were exposed via the
`syn` dict. That meant most chart types couldn't be dialed in from the UI at
all, which is specifically why km_curve got dropped upstream instead of
tuned into something that reads fine: nobody could adjust its rate/steepness
without editing Python.

This module is the schema: one entry per chart, one sub-entry per tunable
value, each describing how to render + validate it as a Streamlit control.
`chart_generators.py` reads `cfg["chart_params"][chart_name]` at render time
instead of hardcoding; `pages/chart_lab.py` renders controls generically
from this schema instead of hand-writing a UI block per chart.

Schema tuple shape: (kind, dtype, lo, hi, step, default, label)
  kind  : "range" -> default is a (lo, hi) pair, rendered as a two-handle
          slider (st.slider supports this natively for a tuple value).
          "value" -> default is a scalar.
  dtype : "int" or "float" -- keeps every bound/step/default/current value
          in the same slider consistently typed (Streamlit infers int vs
          float slider behavior from the types passed in, and mixing them
          raises).
"""

from __future__ import annotations

CHART_PARAM_SCHEMAS: dict[str, dict[str, tuple]] = {
    "bar_chart": {
        "sig_control": ("range", "float", 0.0, 10.0, 0.1, [3.0, 5.0], "TRUE control range"),
        "sig_treatment": ("range", "float", 0.0, 15.0, 0.1, [7.0, 10.0], "TRUE treatment range"),
        "sig_err": ("range", "float", 0.0, 2.0, 0.05, [0.3, 0.8], "TRUE error-bar range"),
        "null_base": ("range", "float", 0.0, 10.0, 0.1, [4.0, 7.0], "FALSE base-value range"),
        "null_jitter": ("value", "float", 0.0, 2.0, 0.05, 0.5, "FALSE control/treatment jitter"),
        "null_err": ("range", "float", 0.0, 4.0, 0.1, [1.0, 2.5], "FALSE error-bar range"),
    },
    "scatter_plot": {
        "n": ("range", "int", 10, 150, 1, [35, 70], "Point count"),
        "sig_slope": ("range", "float", 0.0, 3.0, 0.05, [0.6, 1.2], "TRUE slope range"),
        "sig_noise": ("value", "float", 0.0, 2.0, 0.05, 0.35, "TRUE noise sigma"),
        "null_noise": ("value", "float", 0.0, 3.0, 0.05, 1.0, "FALSE noise sigma"),
    },
    "scatter_plot_2": {
        "n": ("range", "int", 10, 150, 1, [40, 80], "Point count"),
        "sig_slope": ("range", "float", 0.0, 3.0, 0.05, [0.5, 1.5], "TRUE slope range"),
        "sig_noise": ("value", "float", 0.0, 3.0, 0.05, 1.2, "TRUE noise sigma"),
        "null_noise": ("value", "float", 0.0, 5.0, 0.1, 2.5, "FALSE noise sigma"),
    },
    "gaussian_curves": {
        "sig_mu_a": ("value", "float", -6.0, 6.0, 0.1, -2.0, "TRUE Group A mean"),
        "sig_mu_b": ("value", "float", -6.0, 6.0, 0.1, 2.4, "TRUE Group B mean"),
        "sig_sigma": ("range", "float", 0.1, 3.0, 0.05, [0.6, 0.85], "TRUE sigma range"),
        "null_mu_a": ("range", "float", -3.0, 3.0, 0.05, [-1.0, -0.7], "FALSE Group A mean range"),
        "null_gap": ("range", "float", 0.0, 4.0, 0.05, [1.4, 1.9], "FALSE mean-gap range"),
        "null_sigma": ("range", "float", 0.1, 3.0, 0.05, [1.35, 1.7], "FALSE sigma range"),
    },
    "box_plot": {
        "n": ("range", "int", 10, 150, 1, [30, 80], "Sample size"),
        "sig_a_center": ("value", "float", 0.0, 10.0, 0.1, 3.0, "TRUE Control center"),
        "sig_b_center": ("value", "float", 0.0, 10.0, 0.1, 6.5, "TRUE Treatment center"),
        "sig_spread": ("value", "float", 0.1, 3.0, 0.05, 0.8, "TRUE spread"),
        "null_center": ("range", "float", 0.0, 10.0, 0.1, [3.0, 6.0], "FALSE center range"),
        "null_offset": ("value", "float", 0.0, 2.0, 0.05, 0.3, "FALSE control/treatment offset"),
        "null_spread": ("value", "float", 0.1, 3.0, 0.05, 1.5, "FALSE spread"),
    },
    "gap_chart": {
        "pre_noise": ("value", "float", 0.0, 1.0, 0.01, 0.18, "Pre-period noise"),
        "sig_effect": ("range", "float", 0.0, 4.0, 0.1, [1.4, 2.6], "TRUE effect-size range"),
        "sig_post_noise": ("value", "float", 0.0, 1.0, 0.01, 0.12, "TRUE post-period noise"),
        "null_post_noise": ("value", "float", 0.0, 1.0, 0.01, 0.22, "FALSE post-period noise"),
    },
    "synthetic_control": {
        "periods": ("value", "int", 8, 40, 1, 20, "Periods"),
        "intervention": ("value", "int", 2, 30, 1, 10, "Intervention at t="),
        "placebos": ("value", "int", 2, 40, 1, 12, "Placebo count"),
        "sigma": ("value", "float", 0.02, 1.0, 0.01, 0.23, "Placebo cloud sigma"),
        "lw": ("value", "float", 0.3, 3.0, 0.1, 1.3, "Placebo line weight"),
        "alpha": ("value", "float", 0.02, 0.6, 0.01, 0.15, "Placebo cloud alpha"),
        "effect_lw": ("value", "float", 0.3, 5.0, 0.1, 1.8, "Effect line weight"),
        "sig_sigma": ("value", "float", 0.02, 1.0, 0.01, 0.15, "TRUE effect noise sigma"),
        "null_sigma": ("value", "float", 0.02, 1.0, 0.01, 0.23, "FALSE effect noise sigma"),
        "toe": ("value", "float", 0.0, 1.0, 0.01, 0.1, "Take-off (start of divergence)"),
        "div_min": ("value", "float", 0.0, 3.0, 0.05, 1.0, "Divergence min"),
        "div_max": ("value", "float", 0.0, 4.0, 0.05, 1.5, "Divergence max"),
    },
    "forest_plot": {
        "n": ("range", "int", 2, 20, 1, [6, 9], "Study count"),
        "sig_center": ("range", "float", 0.0, 3.0, 0.05, [0.45, 1.5], "TRUE effect-size range"),
        "null_center": ("range", "float", -1.0, 1.0, 0.02, [-0.35, 0.35], "FALSE effect-size range"),
        "err": ("range", "float", 0.0, 1.5, 0.02, [0.15, 0.5], "CI half-width range"),
    },
    "did_parallel_trends": {
        "slope": ("range", "float", 0.0, 1.0, 0.01, [0.12, 0.22], "Parallel pre-trend slope range"),
        "c0": ("range", "float", 0.0, 3.0, 0.05, [0.8, 1.2], "Baseline intercept range"),
        "gap0": ("range", "float", 0.0, 4.0, 0.05, [1.4, 1.9], "Treated/control vertical gap range"),
        "sig_divergence": ("range", "float", 0.0, 4.0, 0.05, [1.0, 1.7], "TRUE post-intervention divergence range"),
        "null_noise": ("value", "float", 0.0, 1.0, 0.01, 0.05, "FALSE post-intervention noise"),
    },
    "event_study": {
        "pre_noise": ("value", "float", 0.0, 1.0, 0.01, 0.06, "Pre-period noise"),
        "sig_effect": ("range", "float", 0.0, 4.0, 0.05, [1.3, 2.0], "TRUE effect-size range"),
        "sig_noise": ("value", "float", 0.0, 1.0, 0.01, 0.05, "TRUE post-period noise"),
        "sig_err_pre": ("range", "float", 0.0, 1.0, 0.02, [0.16, 0.26], "TRUE pre-period CI range"),
        "sig_err_post": ("range", "float", 0.0, 1.0, 0.02, [0.16, 0.30], "TRUE post-period CI range"),
        "null_noise": ("value", "float", 0.0, 1.0, 0.01, 0.10, "FALSE post-period noise"),
        "null_err": ("range", "float", 0.0, 1.0, 0.02, [0.22, 0.40], "FALSE CI range"),
    },
    # Restored (was dropped upstream as "reads as medical-specific") — now
    # fully tunable so it can be dialed into something that reads as general
    # science texture instead of a clinical survival curve.
    "km_curve": {
        "t_max": ("value", "int", 4, 30, 1, 10, "Time horizon"),
        "n_points": ("value", "int", 10, 120, 2, 44, "Curve resolution (points)"),
        "sig_rate_a": ("range", "float", 0.02, 1.0, 0.01, [0.12, 0.20], "TRUE slow-decline rate range"),
        "sig_rate_b": ("range", "float", 0.02, 1.5, 0.01, [0.5, 0.7], "TRUE fast-decline rate range"),
        "null_rate": ("range", "float", 0.02, 1.5, 0.01, [0.28, 0.4], "FALSE shared decline-rate range"),
        "null_jitter": ("range", "float", 0.5, 1.5, 0.01, [0.92, 1.08], "FALSE rate-jitter range (closeness of the two curves)"),
    },
}


def default_chart_params() -> dict[str, dict]:
    """Build the `chart_params` cfg sub-tree from schema defaults."""
    return {
        chart: {key: spec[5] for key, spec in fields.items()}
        for chart, fields in CHART_PARAM_SCHEMAS.items()
    }


def cast_value(dtype: str, value):
    return int(value) if dtype == "int" else float(value)
