from __future__ import annotations

from lib.config_io import load_defaults
from lib.hypothesis_cards import (
    hypothesis_source,
    load_hypotheses,
    render_hypothesis_atlas_html,
    render_hypothesis_card_html,
    select_hypotheses,
)
from lib.ink_control import audit_print_html


def test_canonical_catalog_has_every_main_and_investor_card() -> None:
    cards = load_hypotheses()

    assert len(cards) == 66
    assert len({card.id for card in cards}) == 66
    assert sum(card.pool == "main" for card in cards) == 49
    assert sum(card.pool == "investor" for card in cards) == 17
    assert cards[0].id == "sugar-hyperactivity"
    assert cards[-1].id == "inv-3d-organs"

    source = hypothesis_source()
    assert source.repository_path == "gquinche/phacker-game/src/constants/gameConfig.ts"
    assert source.branch == "trunk"
    assert len(source.commit) == 40


def test_pool_selection_preserves_canonical_order() -> None:
    cards = load_hypotheses()
    main_cards = select_hypotheses(cards, ["main"])
    investor_cards = select_hypotheses(cards, ["investor"])
    all_selected = select_hypotheses(cards, ["investor", "main"])

    assert len(main_cards) == 49
    assert len(investor_cards) == 17
    assert all(card.pool == "main" for card in main_cards)
    assert all(card.pool == "investor" for card in investor_cards)
    assert all_selected == list(cards)


def test_bilingual_card_uses_the_minimal_information_hierarchy() -> None:
    cfg = load_defaults()
    card = load_hypotheses()[0]

    html = render_hypothesis_card_html(
        card,
        index=1,
        cfg=cfg,
        language="bilingual",
    )

    assert 'data-hypothesis-id="sugar-hyperactivity"' in html
    assert '<span class="hyp-card__brand">P-HACKER</span>' in html
    assert '<span class="hyp-card__number">001</span>' in html
    assert '<div class="hyp-card__subject">NUTRITION</div>' in html
    assert 'lang="en">Sugar causes hyperactivity' in html
    assert 'lang="es">El azúcar causa hiperactividad' in html
    assert "MAIN GAME" not in html
    assert "HYPOTHESIS DOSSIER" not in html
    assert "RECORDS BUREAU" not in html
    assert "hyp-card__id" not in html


def test_default_atlas_contains_every_card_once_and_matching_back_sheets() -> None:
    cfg = load_defaults()
    cards = load_hypotheses()

    html = render_hypothesis_atlas_html(
        cfg,
        cards,
        language="bilingual",
        include_backs=True,
    )

    assert html.count('<section class="tw-page" data-page="back">') == 5
    assert html.count('<section class="tw-page tw-page--hypothesis-back" data-page="back">') == 5
    assert html.count('<section class="tw-page') == 10
    assert "RECORDS BUREAU" not in html
    assert "MAIN + INVESTOR" not in html
    for card in cards:
        assert html.count(f'data-hypothesis-id="{card.id}"') == 1

    audit = audit_print_html(html, cfg)
    assert audit["safe"], [warning.message for warning in audit["warnings"]]


def test_front_only_atlas_uses_selected_language_and_pool() -> None:
    cfg = load_defaults()
    cards = select_hypotheses(load_hypotheses(), ["investor"])

    html = render_hypothesis_atlas_html(
        cfg,
        cards,
        language="es",
        include_backs=False,
    )

    assert html.count('<section class="tw-page" data-page="back">') == 2
    assert "tw-page--hypothesis-back" not in html
    assert "Un nuevo fármaco cura las migrañas" in html
    assert "New drug cures migraines" not in html
