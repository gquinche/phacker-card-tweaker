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
                {"chart": "bar_chart", "difference": True, "negative_space": False, "seed": 7},
                {"chart": "bar_chart", "difference": False, "negative_space": False, "seed": 7},
                {"chart": "box_plot", "difference": True, "negative_space": False, "seed": 7},
                {"chart": "box_plot", "difference": False, "negative_space": False, "seed": 7},
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

    def test_negative_space_fills_around_graphic_and_keeps_paper_chart(self):
        cfg = _cfg()
        standard = card_svg.render_card_svg("bar_chart", True, 0, cfg, size="print")
        negative = card_svg.render_card_svg(
            "bar_chart", True, 0, cfg, size="print", negative_space=True,
        )

        standard_root = ET.fromstring(standard)
        negative_root = ET.fromstring(negative)
        self.assertEqual(standard_root.attrib["data-negative-space"], "false")
        self.assertEqual(negative_root.attrib["data-negative-space"], "true")
        self.assertNotIn('id="negative-space-fill"', standard)
        self.assertIn('<rect id="negative-space-fill"', negative)
        self.assertIn('data-negative-space-meaning="fill-around-graphic"', negative)
        self.assertIn('"negative_space":true', negative)
        self.assertIn('opacity="1.000"', negative)
        self.assertIn(f'fill="{preview_hex(cfg, "effect")}"', negative)
        self.assertIn('stroke="#d9d9d9"', negative)

        negative_spec = card_svg.card_specs(["bar_chart"], 0, [True], negative_space=True)[0]
        self.assertTrue(negative_spec["negative_space"])
        self.assertEqual(
            card_svg.card_filename(1, negative_spec),
            "card-01-bar-chart-difference-negative-space.svg",
        )

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
            self.assertEqual(manifest["negative_space_field"], "negative_space")
            self.assertFalse(manifest["contains_negative_space"])
            self.assertEqual([card["difference"] for card in manifest["cards"]], [True, False])
            self.assertEqual([card["negative_space"] for card in manifest["cards"]], [False, False])

    def test_negative_space_zip_records_variant_and_manifest_flag(self):
        cfg = _cfg()
        specs = card_svg.card_specs(["bar_chart"], 3, [False], negative_space=True)
        svgs = [
            card_svg.render_card_svg(
                str(spec["chart"]),
                bool(spec["difference"]),
                int(spec["seed"]),
                cfg,
                size="hand",
                negative_space=bool(spec["negative_space"]),
            )
            for spec in specs
        ]
        archive_bytes = card_svg.build_cards_zip(specs, svgs, size="hand")

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            self.assertIn("card-01-bar-chart-no-difference-negative-space.svg", archive.namelist())
            manifest = json.loads(archive.read("manifest.json"))
            self.assertTrue(manifest["contains_negative_space"])
            self.assertTrue(manifest["cards"][0]["negative_space"])

    def test_invalid_difference_or_size_is_rejected(self):
        cfg = _cfg()
        with self.assertRaises(TypeError):
            card_svg.render_card_svg("bar_chart", "true", 0, cfg)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            card_svg.render_card_svg("bar_chart", True, 0, cfg, negative_space="yes")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            card_svg.card_specs(["bar_chart"], 0, [True], negative_space="yes")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            card_svg.render_card_svg("bar_chart", True, 0, cfg, size="wallet")


if __name__ == "__main__":
    unittest.main()
