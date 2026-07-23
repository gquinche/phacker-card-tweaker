"""Canonical P-Hacker hypothesis data and print-atlas rendering.

The bundled JSON is a reviewed snapshot of ``HYPOTHESIS_POOL`` from
``gquinche/phacker-game``. Keeping the snapshot in this public Streamlit repo
makes PDF generation deterministic and available when GitHub is offline; the
source commit is recorded in the file and surfaced in the UI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Iterable, Sequence

from .card_back_render import card_back_css, render_card_back_html
from .card_render import _FONT_IMPORT, _SERIF, _TYPED
from .config_io import PAGE_SIZES_MM
from .ink_control import preview_hex
from .paper import paper_stock

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "hypotheses.json"
_VALID_LANGUAGES = {"en", "es", "bilingual"}
_VALID_POOLS = {"main", "investor"}


@dataclass(frozen=True)
class HypothesisDef:
    id: str
    subject: str
    en: str
    es: str
    pool: str


@dataclass(frozen=True)
class HypothesisSource:
    repository_path: str
    branch: str
    commit: str


@lru_cache(maxsize=1)
def _load_payload() -> dict:
    with _DATA_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    cards = payload.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("The bundled hypothesis catalog is empty or malformed")
    return payload


@lru_cache(maxsize=1)
def load_hypotheses() -> tuple[HypothesisDef, ...]:
    """Load and validate the canonical hypothesis snapshot."""
    cards = tuple(HypothesisDef(**entry) for entry in _load_payload()["cards"])
    ids = [card.id for card in cards]
    if len(ids) != len(set(ids)):
        raise ValueError("The bundled hypothesis catalog contains duplicate ids")
    unknown_pools = sorted({card.pool for card in cards} - _VALID_POOLS)
    if unknown_pools:
        raise ValueError(f"Unknown hypothesis pools: {', '.join(unknown_pools)}")
    return cards


def hypothesis_source() -> HypothesisSource:
    payload = _load_payload()
    return HypothesisSource(
        repository_path=str(payload["source"]),
        branch=str(payload["source_branch"]),
        commit=str(payload["source_commit"]),
    )


def select_hypotheses(
    cards: Iterable[HypothesisDef],
    pools: Iterable[str],
) -> list[HypothesisDef]:
    """Return selected pools in canonical source order."""
    selected_pools = set(pools)
    unknown = sorted(selected_pools - _VALID_POOLS)
    if unknown:
        raise ValueError(f"Unknown hypothesis pools: {', '.join(unknown)}")
    return [card for card in cards if card.pool in selected_pools]


def _card_title_html(card: HypothesisDef, language: str) -> str:
    if language == "bilingual":
        return (
            f'<h2 class="hyp-card__title" lang="en">{escape(card.en)}</h2>'
            f'<p class="hyp-card__translation" lang="es">{escape(card.es)}</p>'
        )
    title = card.en if language == "en" else card.es
    return f'<h2 class="hyp-card__title hyp-card__title--single" lang="{language}">{escape(title)}</h2>'


def render_hypothesis_card_html(
    card: HypothesisDef,
    *,
    index: int,
    cfg: dict,
    language: str = "bilingual",
) -> str:
    """Render one minimal, print-sized hypothesis card."""
    if language not in _VALID_LANGUAGES:
        raise ValueError(f"Unsupported hypothesis-card language: {language}")
    p = cfg["print"]
    paper = paper_stock(cfg["card"]["paper"])
    ink = preview_hex(cfg, "back")
    subject = card.subject.replace("tech", " tech").upper()
    corner_radius = (
        f'{max(0.0, float(p.get("corner_radius_mm", 3.0))):.2f}mm'
        if p.get("round_corners", False)
        else "0"
    )
    return f"""
<article
  class="hyp-card"
  data-hypothesis-id="{escape(card.id)}"
  data-pool="{card.pool}"
  style="width:{float(p['card_w_mm']):.2f}mm; height:{float(p['card_h_mm']):.2f}mm; color:{ink}; background:{paper['hex']}; border-color:{paper['edge']}; border-radius:{corner_radius};"
>
  <div class="hyp-card__topline">
    <span class="hyp-card__brand">P-HACKER</span>
    <span class="hyp-card__number">{index:03d}</span>
  </div>
  <div class="hyp-card__subject">{escape(subject)}</div>
  <div class="hyp-card__claim">
    {_card_title_html(card, language)}
  </div>
</article>
""".strip()


def _sheet_geometry(cfg: dict) -> tuple[float, float, float, float, float, float, int, int]:
    p = cfg["print"]
    page_w, page_h = PAGE_SIZES_MM[p["page"]]
    bleed = float(p["bleed_mm"])
    cell_w = float(p["card_w_mm"]) + bleed * 2
    cell_h = float(p["card_h_mm"]) + bleed * 2
    cols, rows = int(p["cols"]), int(p["rows"])
    if cols < 1 or rows < 1:
        raise ValueError("Print rows and columns must produce at least one cell")
    grid_w, grid_h = cols * cell_w, rows * cell_h
    grid_left = (page_w - grid_w) / 2
    grid_top = (page_h - grid_h) / 2
    if grid_left < 0 or grid_top < 12:
        raise ValueError(
            "The selected card size, bleed, and grid do not fit the page with room for the sheet header"
        )
    return page_w, page_h, cell_w, cell_h, grid_left, grid_top, cols, rows


def render_hypothesis_atlas_html(
    cfg: dict,
    cards: Sequence[HypothesisDef],
    *,
    language: str = "bilingual",
    include_backs: bool = True,
) -> str:
    """Render all selected hypotheses into one print-sheet HTML document."""
    if language not in _VALID_LANGUAGES:
        raise ValueError(f"Unsupported hypothesis-card language: {language}")
    if not cards:
        raise ValueError("Hypothesis-card export requires at least one card")

    page_w, page_h, cell_w, cell_h, grid_left, grid_top, cols, rows = _sheet_geometry(cfg)
    capacity = cols * rows
    sheets = [cards[start:start + capacity] for start in range(0, len(cards), capacity)]
    sheet_count = len(sheets)
    grid_w = cols * cell_w
    back_ink = preview_hex(cfg, "back")
    token = cfg["card"].get("back_texture", "tex-chevron")
    def header(title: str, meta: str) -> str:
        return f"""
<header class="hyp-sheet__header" style="left:{grid_left:.2f}mm; width:{grid_w:.2f}mm; top:{max(2.0, grid_top - 10.0):.2f}mm; color:{back_ink};">
  <span class="hyp-sheet__kicker">P-HACKER</span>
  <span class="hyp-sheet__title">{title}</span>
  <span class="hyp-sheet__meta">{meta}</span>
</header>""".strip()

    front_pages = []
    for sheet_index, sheet_cards in enumerate(sheets, start=1):
        start_index = (sheet_index - 1) * capacity
        cells = []
        for local_index, card in enumerate(sheet_cards, start=1):
            card_html = render_hypothesis_card_html(
                card,
                index=start_index + local_index,
                cfg=cfg,
                language=language,
            )
            cells.append(f'<div class="hyp-cell">{card_html}</div>')
        meta = f"{len(cards)} CARDS · SHEET {sheet_index}/{sheet_count}"
        front_pages.append(f"""
<section class="tw-page" data-page="back">
  {header("HYPOTHESIS CARDS", meta)}
  <div class="hyp-grid" style="grid-template-columns:repeat({cols}, {cell_w:.2f}mm); grid-template-rows:repeat({rows}, {cell_h:.2f}mm); left:{grid_left:.2f}mm; top:{grid_top:.2f}mm;">
    {''.join(cells)}
  </div>
</section>""".strip())

    back_pages = []
    if include_backs:
        for sheet_index, sheet_cards in enumerate(sheets, start=1):
            cells = []
            for local_index, _card in enumerate(sheet_cards, start=1):
                back_html = render_card_back_html(
                    cfg=cfg,
                    token=token,
                    size="print",
                    uid=f"hypothesis-back-{sheet_index}-{local_index}",
                )
                cells.append(f'<div class="hyp-cell">{back_html}</div>')
            meta = f"{len(cards)} CARDS · SHEET {sheet_index}/{sheet_count}"
            back_pages.append(f"""
<section class="tw-page tw-page--hypothesis-back" data-page="back">
  {header("CARD BACKS", meta)}
  <div class="hyp-grid" style="grid-template-columns:repeat({cols}, {cell_w:.2f}mm); grid-template-rows:repeat({rows}, {cell_h:.2f}mm); left:{grid_left:.2f}mm; top:{grid_top:.2f}mm;">
    {''.join(cells)}
  </div>
</section>""".strip())

    paper = paper_stock(cfg["card"]["paper"])
    body = "".join(front_pages + back_pages)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">{_FONT_IMPORT}<style>
@page {{ size:{page_w}mm {page_h}mm; margin:0; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ margin:0; }}
.tw-page {{
  width:{page_w}mm;
  height:{page_h}mm;
  position:relative;
  overflow:hidden;
  flex:0 0 auto;
  background:#FFFFFF;
  page-break-after:always;
}}
.tw-page:last-child {{ page-break-after:avoid; }}
.hyp-sheet__header {{
  position:absolute;
  z-index:2;
  display:grid;
  grid-template-columns:1fr auto;
  align-items:end;
  gap:0 4mm;
  border-bottom:0.35mm solid currentColor;
  padding-bottom:1.2mm;
  font-family:{_SERIF};
}}
.hyp-sheet__kicker {{
  grid-column:1 / -1;
  font-family:{_TYPED};
  font-size:2.1mm;
  font-weight:700;
  letter-spacing:0.18em;
}}
.hyp-sheet__title {{ font-size:5.1mm; font-weight:700; letter-spacing:0.05em; line-height:1; }}
.hyp-sheet__meta {{ font-family:{_TYPED}; font-size:2.1mm; letter-spacing:0.06em; white-space:nowrap; }}
.hyp-grid {{ display:grid; position:absolute; gap:0; }}
.hyp-cell {{
  display:flex;
  align-items:center;
  justify-content:center;
  border:0.3pt dashed rgba(0,0,0,.15);
}}
.hyp-card {{
  position:relative;
  display:flex;
  flex-direction:column;
  overflow:hidden;
  border-width:0.25mm;
  border-style:solid;
  padding:3.4mm;
  font-family:{_SERIF};
}}
.hyp-card__topline {{
  display:flex;
  align-items:baseline;
  justify-content:space-between;
  gap:3mm;
  padding-bottom:1.6mm;
  border-bottom:0.2mm solid currentColor;
}}
.hyp-card__brand {{
  font-family:{_SERIF};
  font-size:2.8mm;
  font-weight:700;
  letter-spacing:0.08em;
}}
.hyp-card__number {{
  font-family:{_TYPED};
  font-size:2.25mm;
  font-weight:700;
  letter-spacing:0.08em;
}}
.hyp-card__subject {{
  margin-top:2.6mm;
  font-family:{_TYPED};
  font-size:2.0mm;
  font-weight:700;
  letter-spacing:0.16em;
  text-align:center;
}}
.hyp-card__claim {{
  display:flex;
  flex:1;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  min-height:0;
  padding:2.4mm 0 1.2mm;
  text-align:center;
}}
.hyp-card__title {{
  font-size:4.1mm;
  font-weight:700;
  line-height:1.08;
  text-wrap:balance;
}}
.hyp-card__title--single {{ font-size:4.6mm; }}
.hyp-card__translation {{
  margin-top:2.4mm;
  padding-top:2.4mm;
  border-top:0.2mm solid rgba(0,0,0,.25);
  font-size:3.35mm;
  font-style:italic;
  line-height:1.08;
  text-wrap:balance;
}}
@media screen {{
  body {{
    min-height:100vh;
    padding:10mm;
    display:flex;
    flex-direction:column;
    align-items:center;
    gap:10mm;
    background:#d7d4ce;
  }}
  .tw-page {{
    box-shadow:0 2mm 7mm rgba(35,31,25,0.24);
    outline:0.25mm solid rgba(0,0,0,0.12);
  }}
  .hyp-card {{ box-shadow:0 1mm 2.5mm rgba(35,31,25,0.18); }}
}}
{card_back_css(cfg, token)}
</style></head><body style="background:{paper['hex']};">
{body}
</body></html>"""
