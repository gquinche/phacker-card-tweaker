import copy
import sys
import types
import unittest

fake_streamlit = types.SimpleNamespace(session_state={})
sys.modules["streamlit"] = fake_streamlit
sys.modules.setdefault(
    "yaml",
    types.SimpleNamespace(safe_load=lambda text: {}, dump=lambda *args, **kwargs: ""),
)

from lib.config_io import FALLBACK_CONFIG, _merge_defaults
from lib.dice_render import DEFAULT_FACE_SPECS
from lib.editor_state import current_config, load_config_into_widgets


class DiceEditorStateTests(unittest.TestCase):
    def setUp(self):
        fake_streamlit.session_state.clear()
        load_config_into_widgets(copy.deepcopy(FALLBACK_CONFIG))

    def test_six_face_widgets_round_trip_into_nested_config(self):
        fake_streamlit.session_state["dice_background"] = "#112233"
        fake_streamlit.session_state["dice_colored_outlines"] = False
        fake_streamlit.session_state["dice_face_1_chart"] = "forest_plot"
        fake_streamlit.session_state["dice_face_1_significant"] = False
        fake_streamlit.session_state["dice_face_1_seed"] = 42

        cfg = current_config()

        self.assertEqual(cfg["dice"]["background"], "#112233")
        self.assertFalse(cfg["dice"]["colored_outlines"])
        self.assertEqual(cfg["dice"]["faces"][0], {
            "chart": "forest_plot", "significant": False, "seed": 42,
        })
        self.assertEqual(len(cfg["dice"]["faces"]), 6)

    def test_loading_config_clears_cached_atlas_and_individual_exports(self):
        for key in (
            "_last_pdf",
            "_last_pdf_config",
            "_last_individual_pdf_zip",
            "_last_individual_pdf_zip_config",
        ):
            fake_streamlit.session_state[key] = b"stale"

        load_config_into_widgets(copy.deepcopy(FALLBACK_CONFIG))

        self.assertFalse(any(key.startswith("_last_") for key in fake_streamlit.session_state))

    def test_fallback_and_renderer_defaults_stay_in_sync(self):
        self.assertEqual(FALLBACK_CONFIG["dice"]["faces"], [
            dict(spec) for spec in DEFAULT_FACE_SPECS
        ])

    def test_old_or_partial_dice_yaml_is_normalized_to_six_safe_faces(self):
        cfg = _merge_defaults({
            "dice": {
                "background": "not-a-color",
                "colored_outlines": "yes",
                "faces": [{"chart": "box_plot", "significant": False, "seed": 42}],
            },
        })
        self.assertEqual(cfg["dice"]["background"], "#f7f4ec")
        self.assertTrue(cfg["dice"]["colored_outlines"])
        self.assertEqual(cfg["dice"]["faces"][0], {
            "chart": "box_plot", "significant": False, "seed": 42,
        })
        self.assertEqual(cfg["dice"]["faces"][1:], [
            dict(spec) for spec in DEFAULT_FACE_SPECS[1:]
        ])


if __name__ == "__main__":
    unittest.main()
