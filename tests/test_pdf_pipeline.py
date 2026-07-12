from pathlib import Path
import unittest

from lib.ink_control import _remove_screen_media, audit_print_html
from lib.pdf_pipeline import _ghostscript_command


class PdfPipelineTests(unittest.TestCase):
    def test_ghostscript_command_requests_vector_cmyk_output(self):
        command = _ghostscript_command(
            "/usr/bin/gs",
            Path("source.pdf"),
            Path("output.pdf"),
            None,
        )
        self.assertIn("-sDEVICE=pdfwrite", command)
        self.assertIn("-dProcessColorModel=/DeviceCMYK", command)
        self.assertIn("-sColorConversionStrategy=CMYK", command)
        self.assertIn("-sColorConversionStrategyForImages=CMYK", command)
        self.assertEqual(command[-1], "source.pdf")

    def test_screen_media_is_removed_with_nested_rules(self):
        css = "body { color: #000000; } @media screen { .card { box-shadow: 0 0 2px red; } .x { color: blue; } } .print { color: #111111; }"
        stripped = _remove_screen_media(css)
        self.assertIn("#000000", stripped)
        self.assertIn("#111111", stripped)
        self.assertNotIn("box-shadow", stripped)
        self.assertNotIn("blue", stripped)

    def test_ink_audit_ignores_screen_only_colors(self):
        cfg = {
            "cmyk": {
                "effect": [50, 26, 0, 49],
                "no_effect": [0, 0, 0, 54],
                "back": [0, 0, 0, 83],
            },
            "print": {
                "ink_policy": {
                    "effect": ["C", "M", "K"],
                    "no_effect": ["K"],
                    "back": ["K"],
                }
            },
        }
        html = """<style>
        .print { color: #767676; }
        @media screen { .print { box-shadow: 0 0 3px #ff0000; color: #00ff00; } }
        </style>
        <section class="tw-page" data-page="no_effect"><div style="color:#767676"></div></section>"""
        audit = audit_print_html(html, cfg)
        self.assertTrue(audit["safe"], audit["warnings"])


if __name__ == "__main__":
    unittest.main()
