import copy
import sys
import types
import unittest

# Keep this focused parity test runnable in the lightweight sandbox even when
# the full Streamlit dependency set has not been installed yet.
sys.modules.setdefault(
    "yaml",
    types.SimpleNamespace(safe_load=lambda text: {}, dump=lambda *args, **kwargs: ""),
)

from lib.card_render import render_individual_card_pages_html, render_print_atlas_html
from lib.config_io import FALLBACK_CONFIG
from lib.ink_control import audit_print_html


class CardRenderParityTests(unittest.TestCase):
    def test_preview_and_pdf_targets_produce_identical_canonical_html(self):
        cfg = copy.deepcopy(FALLBACK_CONFIG)
        cfg["print"]["include_back_pages"] = False
        sig_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#426183"/></svg>'
        null_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#767676"/></svg>'

        preview = render_print_atlas_html(cfg, [sig_svg], [null_svg], target="preview")
        pdf = render_print_atlas_html(cfg, [sig_svg], [null_svg], target="pdf")

        self.assertEqual(preview, pdf)
        self.assertNotIn("device-cmyk(", preview)
        self.assertTrue(audit_print_html(preview, cfg)["safe"])

    def test_atlas_paginates_every_distinct_card_without_cycling(self):
        cfg = copy.deepcopy(FALLBACK_CONFIG)
        cfg["print"]["cols"] = 2
        cfg["print"]["rows"] = 2
        cfg["print"]["include_back_pages"] = False
        sig_svgs = [f'<svg data-source="sig-{index}"></svg>' for index in range(5)]
        null_svgs = [f'<svg data-source="null-{index}"></svg>' for index in range(6)]

        html = render_print_atlas_html(cfg, sig_svgs, null_svgs)

        self.assertEqual(html.count('data-page="effect"'), 2)
        self.assertEqual(html.count('data-page="no_effect"'), 2)
        for index in range(5):
            self.assertEqual(html.count(f'data-source="sig-{index}"'), 1)
        for index in range(6):
            self.assertEqual(html.count(f'data-source="null-{index}"'), 1)
        self.assertNotIn("E05", html)
        self.assertNotIn("N06", html)

    def test_atlas_back_sheets_match_each_front_sheet_card_count(self):
        cfg = copy.deepcopy(FALLBACK_CONFIG)
        cfg["print"]["cols"] = 2
        cfg["print"]["rows"] = 2
        cfg["print"]["include_back_pages"] = True
        sig_svgs = [f'<svg data-source="sig-{index}"></svg>' for index in range(5)]
        null_svgs = [f'<svg data-source="null-{index}"></svg>' for index in range(6)]

        html = render_print_atlas_html(cfg, sig_svgs, null_svgs)

        self.assertEqual(html.count('data-page="back"'), 4)
        self.assertEqual(html.count('class="tw-card-back tw-card-back--print"'), 11)

    def test_individual_export_orders_each_front_before_its_matching_back(self):
        cfg = copy.deepcopy(FALLBACK_CONFIG)
        cfg["print"]["include_back_pages"] = True
        cards = [
            ("E00", True, '<svg data-source="effect"></svg>'),
            ("N00", False, '<svg data-source="no-effect"></svg>'),
        ]

        html = render_individual_card_pages_html(cfg, cards)

        self.assertEqual(html.count('<section class="tw-page"'), 4)
        self.assertLess(
            html.index('data-page="effect" data-card-id="E00"'),
            html.index('data-page="back" data-card-id="E00"'),
        )
        self.assertLess(
            html.index('data-page="no_effect" data-card-id="N00"'),
            html.index('data-page="back" data-card-id="N00"'),
        )
        self.assertIn("@page { size: 47.27mm 63.79mm; margin: 0; }", html)
        self.assertTrue(audit_print_html(html, cfg)["safe"])

    def test_individual_export_can_generate_front_only_pages(self):
        cfg = copy.deepcopy(FALLBACK_CONFIG)
        cfg["print"]["include_back_pages"] = False
        cards = [
            ("E00", True, '<svg data-source="effect"></svg>'),
            ("N00", False, '<svg data-source="no-effect"></svg>'),
        ]

        html = render_individual_card_pages_html(cfg, cards)

        self.assertEqual(html.count('<section class="tw-page"'), 2)
        self.assertNotIn('data-page="back"', html)


if __name__ == "__main__":
    unittest.main()
