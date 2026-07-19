import io
import json
import unittest
import xml.etree.ElementTree as ET
import zipfile

from lib import card_svg
from lib.chart_params import default_chart_params
from lib.ink_control import preview_hex


SVG_NS = "{http://www.w3.org/2000/svg}"


def _cfg():
    return {
        "palette": {"SIG": "#426183", "NULL": "#767676"},
        "cmyk": {
            "effect": [50, 26, 0, 49],
            "no_effect": [0, 0, 0, 54],
        },
        "hatch": {"bar": ["///", "|||"], "box": ["///", "+++"], "gauss": "/"},
        "hatch_lw": 2.2,
        "band_pct": 20,
        "chart_params": default_chart_params(),
        "card": {
            "paper": "white",
            "chart_opacity": 0.6,
            "show_footer": False,
            "show_stamp": True,
            "show_creases": True,
        },
        "print": {
            "round_corners": False,
            "corner_radius_mm": 3.0,
            "show_card_id": True,
        },
    }


class CardSvgTests(unittest.TestCase):
    def test_card_specs_use_boolean_difference_field(self):
        specs = card_svg.card_specs(
            ["bar_chart", "not-a-chart", "box_plot"],
            7,
            [True, False, True],
        )
        self.assertEqual(
            specs,
            [
                {"chart": "bar_chart", "difference": True, "seed": 7},
                {"chart": "bar_chart", "difference": False, "seed": 7},
                {"chart": "box_plot", "difference": True, "seed": 7},
                {"chart": "box_plot", "difference": False, "seed": 7},
            ],
        )
        self.assertTrue(all(isinstance(spec["difference"], bool) for spec in specs))

    def test_rendered_card_has_paper_infill_border_and_difference_metadata(self):
        cfg = _cfg()
        difference = card_svg.render_card_svg("bar_chart", True, 0, cfg, size="print")
        no_difference = card_svg.render_card_svg("bar_chart", False, 0, cfg, size="print")

        for svg, expected in ((difference, "true"), (no_difference, "false")):
            root = ET.fromstring(svg)
            self.assertEqual(root.attrib["data-difference"], expected)
            self.assertIsNotNone(root.find(f"{SVG_NS}rect[@id='card-infill']"))
            self.assertIsNotNone(root.find(f"{SVG_NS}rect[@id='card-border']"))
            self.assertIn('"difference":' + expected, svg)
            self.assertIn("DIFFERENCE" if expected == "true" else "NO DIFFERENCE", svg)

        self.assertIn("#ffffff", difference)
        self.assertIn("#d9d9d9", difference)
        self.assertIn(preview_hex(cfg, "effect"), difference)
        self.assertIn(preview_hex(cfg, "no_effect"), no_difference)
        self.assertNotEqual(preview_hex(cfg, "effect"), preview_hex(cfg, "no_effect"))

    def test_card_svg_zip_manifest_describes_border_infill_and_boolean_field(self):
        cfg = _cfg()
        specs = card_svg.card_specs(["bar_chart"], 3, [True, False])
        svgs = [
            card_svg.render_card_svg(
                str(spec["chart"]),
                bool(spec["difference"]),
                int(spec["seed"]),
                cfg,
                size="hand",
            )
            for spec in specs
        ]
        archive_bytes = card_svg.build_cards_zip(specs, svgs, size="hand")

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            self.assertEqual(
                sorted(name for name in archive.namelist() if name.endswith(".svg")),
                [
                    "card-01-bar-chart-difference.svg",
                    "card-02-bar-chart-no-difference.svg",
                ],
            )
            manifest = json.loads(archive.read("manifest.json"))
            self.assertTrue(manifest["border"])
            self.assertTrue(manifest["infill"])
            self.assertEqual(manifest["difference_field"], "difference")
            self.assertEqual([card["difference"] for card in manifest["cards"]], [True, False])

    def test_invalid_difference_or_size_is_rejected(self):
        cfg = _cfg()
        with self.assertRaises(TypeError):
            card_svg.render_card_svg("bar_chart", "true", 0, cfg)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            card_svg.render_card_svg("bar_chart", True, 0, cfg, size="wallet")


if __name__ == "__main__":
    unittest.main()
