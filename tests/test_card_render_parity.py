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

from lib.card_render import render_print_atlas_html
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


if __name__ == "__main__":
    unittest.main()
