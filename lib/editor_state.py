"""Map ordinary Streamlit widget keys to the exported card configuration.

Widgets own the live values. Rendering and export call :func:`current_config`
to collect those values into the nested YAML shape. There is no second mutable
`cfg` object competing with Streamlit's widget state.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import streamlit as st

from .colors import cmyk_to_hex

_CONFIG_TEMPLATE_KEY = "config_template"
_PARAM_PREFIX = "param_"

# One stable Streamlit key per exported scalar/list setting. Dynamic per-chart
# parameters use `param_<chart>_<name>` and are collected separately below.
WIDGET_PATHS: dict[str, tuple[str, ...]] = {
    "card_paper": ("card", "paper"),
    "band_pct": ("band_pct",),
    "card_chart_opacity": ("card", "chart_opacity"),
    "card_back_texture": ("card", "back_texture"),
    "card_show_footer": ("card", "show_footer"),
    "card_show_stamp": ("card", "show_stamp"),
    "card_show_creases": ("card", "show_creases"),
    "dpi": ("dpi",),
    "hatch_lw": ("hatch_lw",),
    "hatch_bar_control": ("hatch", "bar", "0"),
    "hatch_bar_treatment": ("hatch", "bar", "1"),
    "hatch_box_control": ("hatch", "box", "0"),
    "hatch_box_treatment": ("hatch", "box", "1"),
    "hatch_gauss": ("hatch", "gauss"),
    "effect_c": ("cmyk", "effect", "0"),
    "effect_m": ("cmyk", "effect", "1"),
    "effect_y": ("cmyk", "effect", "2"),
    "effect_k": ("cmyk", "effect", "3"),
    "no_effect_c": ("cmyk", "no_effect", "0"),
    "no_effect_m": ("cmyk", "no_effect", "1"),
    "no_effect_y": ("cmyk", "no_effect", "2"),
    "no_effect_k": ("cmyk", "no_effect", "3"),
    "back_c": ("cmyk", "back", "0"),
    "back_m": ("cmyk", "back", "1"),
    "back_y": ("cmyk", "back", "2"),
    "back_k": ("cmyk", "back", "3"),
    "print_cols": ("print", "cols"),
    "print_rows": ("print", "rows"),
    "print_page": ("print", "page"),
    "print_card_w_mm": ("print", "card_w_mm"),
    "print_card_h_mm": ("print", "card_h_mm"),
    "print_bleed_mm": ("print", "bleed_mm"),
    "print_use_cmyk": ("print", "use_cmyk"),
    "print_show_calibration_strip": ("print", "show_calibration_strip"),
    "print_show_card_id": ("print", "show_card_id"),
    "print_include_back_pages": ("print", "include_back_pages"),
    "print_round_corners": ("print", "round_corners"),
    "print_corner_radius_mm": ("print", "corner_radius_mm"),
    "print_strict_ink_check": ("print", "strict_ink_check"),
    "effect_allowed_channels": ("print", "ink_policy", "effect"),
    "no_effect_allowed_channels": ("print", "ink_policy", "no_effect"),
    "back_allowed_channels": ("print", "ink_policy", "back"),
}


def param_widget_key(chart_name: str, param_name: str) -> str:
    return f"{_PARAM_PREFIX}{chart_name}_{param_name}"


def _widget_value(value: Any) -> Any:
    """Convert exported range lists to Streamlit's native tuple value."""
    return tuple(value) if isinstance(value, list) else deepcopy(value)


def _seed_missing_widget_values(template: dict) -> None:
    """Restore keys that are absent when a session starts or imports config."""
    for key, path in WIDGET_PATHS.items():
        if key not in st.session_state:
            st.session_state[key] = deepcopy(_get_path(template, path))

    for chart_name, params in template.get("chart_params", {}).items():
        for param_name, value in params.items():
            key = param_widget_key(chart_name, param_name)
            if key not in st.session_state:
                st.session_state[key] = _widget_value(value)


def _protect_widget_values_from_page_cleanup() -> None:
    """Keep keyed settings alive when their multipage widget is not rendered.

    Streamlit otherwise deletes page-local widget keys and can reconnect a
    returning widget to stale frontend defaults. Re-saving the value in the
    entrypoint is Streamlit's documented multipage persistence pattern.
    """
    for key in list(st.session_state):
        if key in WIDGET_PATHS or key.startswith(_PARAM_PREFIX):
            st.session_state[key] = st.session_state[key]


def _get_path(cfg: dict, path: tuple[str, ...]) -> Any:
    value: Any = cfg
    for part in path:
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _set_path(cfg: dict, path: tuple[str, ...], value: Any) -> None:
    target: Any = cfg
    for part in path[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    final = path[-1]
    if isinstance(target, list):
        target[int(final)] = value
    else:
        target[final] = value


def load_config_into_widgets(cfg: dict) -> None:
    """Replace the editor state from defaults or an imported YAML config."""
    template = deepcopy(cfg)
    st.session_state[_CONFIG_TEMPLATE_KEY] = template
    st.session_state.pop("cfg", None)  # retire the old competing state layer

    for key, path in WIDGET_PATHS.items():
        st.session_state[key] = deepcopy(_get_path(template, path))

    for key in list(st.session_state):
        if key.startswith(_PARAM_PREFIX):
            del st.session_state[key]
    for chart_name, params in template.get("chart_params", {}).items():
        for param_name, value in params.items():
            st.session_state[param_widget_key(chart_name, param_name)] = _widget_value(value)

    st.session_state.pop("_last_pdf", None)


def initialize_editor(cfg: dict) -> None:
    """Initialize settings and preserve them across multipage navigation."""
    if _CONFIG_TEMPLATE_KEY not in st.session_state:
        load_config_into_widgets(cfg)
        return
    _protect_widget_values_from_page_cleanup()
    _seed_missing_widget_values(st.session_state[_CONFIG_TEMPLATE_KEY])


def current_config() -> dict:
    """Collect current widget values into the nested export/render config."""
    cfg = deepcopy(st.session_state[_CONFIG_TEMPLATE_KEY])
    for key, path in WIDGET_PATHS.items():
        if key in st.session_state:
            _set_path(cfg, path, deepcopy(st.session_state[key]))

    for chart_name, params in cfg.get("chart_params", {}).items():
        for param_name in params:
            key = param_widget_key(chart_name, param_name)
            if key in st.session_state:
                value = deepcopy(st.session_state[key])
                params[param_name] = list(value) if isinstance(value, tuple) else value

    # Hex palette is derived from the canonical CMYK slider values.
    cfg["palette"]["SIG"] = cmyk_to_hex(*cfg["cmyk"]["effect"])
    cfg["palette"]["NULL"] = cmyk_to_hex(*cfg["cmyk"]["no_effect"])
    cfg["palette"]["BACK"] = cmyk_to_hex(*cfg["cmyk"]["back"])

    # Keep the last collected snapshot as the import/default template. This is
    # one-way (widgets -> snapshot), so it never fights a widget during reruns
    # and preserves values for page-specific widgets when their page is hidden.
    st.session_state[_CONFIG_TEMPLATE_KEY] = deepcopy(cfg)
    return cfg
