"""Load/save the tweaker's YAML config — the file Alejandro backs up into
phacker-game (tools/card-art/) once values are dialed in. Schema intentionally
mirrors the real pipeline's tunable dicts (PALETTE / HATCH / SYN in
tools/card-art/fake_charts_cardart.py + build_nb.py's notebook cell) so
copying values across is a straight lift, not a translation exercise.
"""

from __future__ import annotations

from pathlib import Path

import yaml

DEFAULTS_PATH = Path(__file__).resolve().parent.parent / "config_defaults.yaml"

FALLBACK_CONFIG: dict = {
    "palette": {"SIG": "#426183", "NULL": "#767676"},
    "cmyk": {
        "effect": [50, 26, 0, 49],      # -> #426183
        "no_effect": [0, 0, 0, 54],     # -> #767676
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
    "syn": {
        "periods": 20, "intervention": 10, "placebos": 12, "sigma": 0.23,
        "lw": 1.3, "alpha": 0.15, "effect_lw": 1.8, "sig_sigma": 0.15,
        "null_sigma": 0.23, "toe": 0.1, "div_min": 1.0, "div_max": 1.5,
    },
    "card": {
        "paper": "cream",           # cream | white | manila
        "chart_opacity": 0.45,      # real shipped .print-card__chart opacity
        "wash_alpha_sig": 0.18,     # real shipped .print-card--significant wash
        "wash_alpha_null": 0.16,   # real shipped .print-card--null wash
        "show_footer": True,
        "show_stamp": True,
        "show_creases": True,
    },
    "print": {
        "card_w_mm": 41.27,
        "card_h_mm": 57.79,
        "bleed_mm": 3.0,
        "cols": 4,
        "rows": 4,
        "page": "A4_portrait",      # A4_portrait | A4_landscape | letter_portrait | letter_landscape
        "use_cmyk": True,
        "show_calibration_strip": False,
        "show_card_id": True,
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
