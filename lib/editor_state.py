"""Small helpers that keep widget drafts separate from the saved card config.

`st.session_state.cfg` is the editor's single durable source of truth. Widgets
use short-lived, underscore-prefixed draft keys so Streamlit can discard and
rehydrate their page-local state without clobbering a loaded config.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import streamlit as st

_CONFIG_WIDGET_PREFIX = "_cfg_"


def config_widget_key(name: str) -> str:
    """Return the stable, namespaced Streamlit key for one config control."""
    return f"{_CONFIG_WIDGET_PREFIX}{name}"


def hydrate_config_widget(name: str, value: Any) -> str:
    """Seed a widget draft from cfg only when the page creates it anew."""
    key = config_widget_key(name)
    if key not in st.session_state:
        st.session_state[key] = deepcopy(value)
    return key


def clear_config_widget_drafts() -> None:
    """Forget page-local widget drafts so the next page run hydrates from cfg."""
    for key in list(st.session_state):
        if key.startswith(_CONFIG_WIDGET_PREFIX):
            del st.session_state[key]


def replace_config(cfg: dict, *, clear_drafts: bool = True) -> None:
    """Install a new config and invalidate output derived from the old config."""
    st.session_state.cfg = cfg
    if clear_drafts:
        clear_config_widget_drafts()
    st.session_state.pop("_last_pdf", None)


def schedule_config_draft_reset() -> None:
    """Clear drafts at the next safe script start before any widget is created."""
    st.session_state["_clear_config_widget_drafts"] = True
