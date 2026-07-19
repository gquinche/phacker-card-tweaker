import copy
import io
import json
import re
import unittest
import xml.etree.ElementTree as ET
import zipfile

from lib import chart_generators as cg
from lib.chart_params import default_chart_params
from lib.dice_render import (
    DEFAULT_FACE_SPECS,
    DICE_NEUTRAL_OUTLINE,
    build_faces_zip,
    face_specs_from_config,
    render_face_svg,
    render_faces,
)


def _cfg():
    return {
        "palette": {"SIG": "#426183", "NULL": "#767676"},
        "hatch": {"bar": ["///", "|||"], "box": ["///", "+++"], "gauss": "/"},
        "hatch_lw": 2.2,
        "chart_params": default_chart_params(),
        "dice": {
            "background": "#f7f4ec",
            "transparent_background": True,
            "colored_outlines": True,
            "negative_space": False,
            "faces": copy.deepcopy(list(DEFAULT_FACE_SPECS)),
        },
    }


class DiceRenderTests(unittest.TestCase):
    def test_default_config_has_exactly_six_valid_faces(self):
        specs = face_specs_from_config(_cfg())
        self.assertEqual(len(specs), 6)
        self.assertTrue(all(spec["chart"] in cg.GENERATOR_NAMES for spec in specs))
        self.assertEqual([spec["chart"] for spec in specs], [
            "gaussian_curves", "box_plot", "bar_chart", "km_curve",
            "forest_plot", "did_parallel_trends",
        ])

    def test_every_chart_family_member_exports_as_parseable_minimal_svg(self):
        cfg = _cfg()
        for index, chart in enumerate(cg.all_chart_names()):
            with self.subTest(chart=chart):
                svg = render_face_svg(
                    chart,
                    index % 2 == 0,
                    index,
                    cfg,
                    background_hex="#ffffff",
                    colored_outlines=True,
                )
                ET.fromstring(svg)
                self.assertIn('viewBox="0 0 256 256"', svg)
                self.assertNotIn("<text", svg)
                self.assertNotIn("font-family", svg)
                self.assertNotIn("hatch", svg.lower())

    def test_color_toggle_switches_between_palette_and_neutral_contours(self):
        cfg = _cfg()
        colored = render_face_svg(
            "gaussian_curves", True, 0, cfg,
            background_hex="#f7f4ec", colored_outlines=True,
            transparent_background=False,
        )
        neutral = render_face_svg(
            "gaussian_curves", True, 0, cfg,
            background_hex="#f7f4ec", colored_outlines=False,
            transparent_background=False,
        )
        self.assertIn("#426183", colored)
        self.assertIn(DICE_NEUTRAL_OUTLINE, neutral)
        self.assertNotIn("#426183", neutral)
        self.assertIn("#f7f4ec", colored)
        self.assertIn("#f7f4ec", neutral)

    def test_negative_space_fills_around_graph_and_redraws_it_in_background_color(self):
        cfg = _cfg()
        negative = render_face_svg(
            "gaussian_curves", True, 0, cfg,
            background_hex="#f7f4ec", colored_outlines=True,
            transparent_background=True, negative_space=True,
        )
        standard = render_face_svg(
            "gaussian_curves", True, 0, cfg,
            background_hex="#f7f4ec", colored_outlines=True,
            transparent_background=True, negative_space=False,
        )
        specs, faces = render_faces({**cfg, "dice": {**cfg["dice"], "negative_space": True}})

        negative_root = ET.fromstring(negative)
        self.assertEqual(negative_root.attrib["data-negative-space"], "true")
        self.assertIn('data-negative-space-meaning="fill-around-graphic"', negative)
        self.assertIn('<rect id="negative-space-fill" x="5" y="5" width="246" height="246" rx="14" fill="#426183"/>', negative)
        self.assertIn('"negative_space":true', negative)
        self.assertIn("#f7f4ec", negative)
        self.assertNotIn('id="negative-space-fill"', standard)
        self.assertEqual(len(specs), 6)
        self.assertTrue(all(spec["negative_space"] for spec in specs))
        self.assertTrue(all('data-negative-space="true"' in svg for svg in faces))
        archive_bytes = build_faces_zip(
            {**cfg, "dice": {**cfg["dice"], "negative_space": True}},
            specs,
            faces,
        )
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertTrue(manifest["negative_space"])
            self.assertTrue(all(face["negative_space"] for face in manifest["faces"]))

    def test_transparent_export_contains_only_graph_and_opaque_fill_remains_borderless(self):
        cfg = _cfg()
        transparent = render_face_svg(
            "gaussian_curves", True, 0, cfg,
            background_hex="#abcdef", colored_outlines=True,
        )
        opaque = render_face_svg(
            "gaussian_curves", True, 0, cfg,
            background_hex="#abcdef", colored_outlines=True,
            transparent_background=False,
        )

        self.assertNotIn('<rect x="5" y="5" width="246"', transparent)
        self.assertNotIn("#abcdef", transparent)
        self.assertIn('<rect width="256" height="256" fill="#abcdef"/>', opaque)
        self.assertNotIn('stroke="#426183" stroke-width="4"', opaque)

    def test_repeated_face_choices_get_distinct_svg_reference_namespaces(self):
        cfg = _cfg()
        duplicate = {"chart": "scatter_plot", "significant": True, "seed": 7}
        cfg["dice"]["faces"][0] = duplicate
        cfg["dice"]["faces"][1] = duplicate
        _, faces = render_faces(cfg)
        references = [set(re.findall(r'(?:xlink:href="#|url\(#)([^)"\s]+)', svg)) for svg in faces[:2]]
        self.assertTrue(references[0])
        self.assertTrue(references[1])
        self.assertTrue(references[0].isdisjoint(references[1]))

    def test_six_face_zip_contains_standalone_svgs_and_manifest(self):
        cfg = _cfg()
        specs, faces = render_faces(cfg)
        self.assertTrue(all('<rect x="5" y="5" width="246"' not in svg for svg in faces))
        archive_bytes = build_faces_zip(cfg, specs, faces)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            self.assertEqual(len([name for name in names if name.endswith(".svg")]), 6)
            self.assertIn("manifest.json", names)
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["background"], "#f7f4ec")
            self.assertTrue(manifest["transparent_background"])
            self.assertTrue(manifest["colored_outlines"])
            self.assertFalse(manifest["negative_space"])
            self.assertEqual(manifest["negative_space_field"], "negative_space")
            self.assertEqual(len(manifest["faces"]), 6)
            self.assertTrue(all(not face["negative_space"] for face in manifest["faces"]))

    def test_partial_or_invalid_old_config_falls_back_safely(self):
        cfg = _cfg()
        cfg["dice"]["faces"] = [{
            "chart": "not-a-chart", "significant": "false", "seed": "bad",
        }]
        specs = face_specs_from_config(cfg)
        self.assertEqual(len(specs), 6)
        self.assertEqual(specs[0], dict(DEFAULT_FACE_SPECS[0]))
        self.assertEqual(specs[5], dict(DEFAULT_FACE_SPECS[5]))

        cfg["dice"]["faces"] = "not-a-list"
        self.assertEqual(face_specs_from_config(cfg), [dict(spec) for spec in DEFAULT_FACE_SPECS])


if __name__ == "__main__":
    unittest.main()
