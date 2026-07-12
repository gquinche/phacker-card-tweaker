"""Load/save the tweaker's YAML config — the file Alejandro backs up into
phacker-game (tools/card-art/) once values are dialed in. Schema intentionally
mirrors the real pipeline's tunable dicts (PALETTE / HATCH / SYN in
tools/card-art/fake_charts_cardart.py + build_nb.py's notebook cell) so
copying values across is a straight lift, not a translation exercise.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .chart_params import default_chart_params

DEFAULTS_PATH = Path(__file__).resolve().parent.parent / "config_defaults.yaml"

FALLBACK_CONFIG: dict = {
    "palette": {"SIG": "#426183", "NULL": "#767676", "BACK": "#2b2b2b"},
    "cmyk": {
        "effect": [50, 26, 0, 49],      # -> #426183
        "no_effect": [0, 0, 0, 54],     # -> #767676
        "back": [0, 0, 0, 83],          # -> #2b2b2b
    },
    "hatch": {
        "bar": ["///", "|||"],
        "box": ["///", "+++"],
        "gauss": "/",
    },
    "hatch_lw": 2.2,
    "dpi": 150,
    "seeds_per_type": 2,
    "band_pct": 20,
    "precolor": True,
    # Per-chart-type tunable params (sample sizes, effect-size ranges, noise
    # levels) — one sub-dict per chart in lib/chart_params.CHART_PARAM_SCHEMAS.
    # This replaces the old top-level `syn` key, which only covered
    # synthetic_control; every chart type is tunable now.
    "chart_params": default_chart_params(),
    "card": {
        "paper": "white",           # white | cream | manila
        "chart_opacity": 0.6,
        "back_texture": "tex-chevron",
        "wash_alpha_sig": 0.18,     # real shipped .print-card--significant wash
        "wash_alpha_null": 0.16,   # real shipped .print-card--null wash
        "show_footer": False,
        "show_stamp": True,
        "show_creases": True,
        # Screen-only atmosphere is applied through @media screen so it never
        # changes the canonical print geometry or CMYK source colors.
        "screen_shadows": True,
        "screen_paper_texture": True,
        "screen_warm_creases": True,
    },
    "print": {
        "card_w_mm": 41.27,
        "card_h_mm": 57.79,
        "bleed_mm": 3.0,
        "cols": 4,
        "rows": 4,
        "page": "A4_portrait",      # A4_portrait | A4_landscape | letter_portrait | letter_landscape
        "use_cmyk": True,
        "pdf_renderer": "auto",       # auto | browser | weasyprint
        "cmyk_profile_path": "",       # optional local ICC profile for Ghostscript
        "show_calibration_strip": False,
        "show_card_id": True,
        "include_back_pages": True,
        "round_corners": False,
        "corner_radius_mm": 3.0,
        "strict_ink_check": True,
        "ink_policy": {
            "effect": ["C", "M", "K"],
            "no_effect": ["K"],
            "back": ["K"],
        },
    },
}


def load_defaults() -> dict:
    if DEFAULTS_PATH.exists():
        with open(DEFAULTS_PATH) as f:
            loaded = yaml.safe_load(f)
            if loaded:
                return _merge_defaults(loaded)
    return _deep_copy(FALLBACK_CONFIG)


def _deep_copy(d):
    import copy
    return copy.deepcopy(d)


def _merge_defaults(loaded: dict) -> dict:
    """Fill in any keys missing from an older/partial YAML with fallback
    values, so opening a config saved before a schema addition doesn't KeyError."""
    merged = _deep_copy(FALLBACK_CONFIG)
    _deep_update(merged, loaded)
    return merged


def _deep_update(base: dict, overlay: dict) -> None:
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v


def load_from_yaml_text(text: str) -> dict:
    loaded = yaml.safe_load(text) or {}
    return _merge_defaults(loaded)


def dump_yaml(cfg: dict) -> str:
    return yaml.dump(cfg, default_flow_style=False, allow_unicode=True, sort_keys=False)


PAGE_SIZES_MM = {
    "A4_portrait": (210.0, 297.0),
    "A4_landscape": (297.0, 210.0),
    "letter_portrait": (215.9, 279.4),
    "letter_landscape": (279.4, 215.9),
}
