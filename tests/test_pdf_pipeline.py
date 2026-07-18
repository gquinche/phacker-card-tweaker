import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import zipfile

from lib.ink_control import _remove_screen_media, audit_print_html
from lib.pdf_pipeline import (
    PdfPipelineError,
    _ghostscript_command,
    build_individual_pdf_zip,
    split_card_pdf_zip,
)


class _FakePdfReader:
    def __init__(self, source):
        page_count = int(source.read().decode("ascii"))
        self.pages = [f"page-{index}" for index in range(page_count)]


class _FakePdfWriter:
    def __init__(self):
        self.pages = []

    def add_page(self, page):
        self.pages.append(page)

    def write(self, destination):
        destination.write("|".join(self.pages).encode("ascii"))


_FAKE_PYPDF = types.SimpleNamespace(PdfReader=_FakePdfReader, PdfWriter=_FakePdfWriter)


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

    def test_split_card_pdf_zip_pairs_front_and_back_pages(self):
        with patch.dict(sys.modules, {"pypdf": _FAKE_PYPDF}):
            archive_bytes = split_card_pdf_zip(
                b"4",
                ["Effect Gaussian", "No Effect Box"],
                pages_per_card=2,
            )

        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"effect-gaussian.pdf", "no-effect-box.pdf", "manifest.json"},
            )
            self.assertEqual(archive.read("effect-gaussian.pdf"), b"page-0|page-1")
            self.assertEqual(archive.read("no-effect-box.pdf"), b"page-2|page-3")
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["pages_per_card"], 2)
            self.assertEqual(len(manifest["cards"]), 2)

    def test_individual_zip_renders_batch_once_before_splitting_front_only_files(self):
        with patch.dict(sys.modules, {"pypdf": _FAKE_PYPDF}):
            with patch("lib.pdf_pipeline.build_pdf_bytes", return_value=b"2") as render_batch:
                archive_bytes = build_individual_pdf_zip(
                    "<html></html>",
                    ["E00", "N00"],
                    include_back_pages=False,
                    renderer="browser",
                    use_cmyk=False,
                )

        render_batch.assert_called_once()
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            self.assertEqual(archive.read("e00.pdf"), b"page-0")
            self.assertEqual(archive.read("n00.pdf"), b"page-1")

    def test_split_card_pdf_zip_rejects_unexpected_page_count(self):
        with patch.dict(sys.modules, {"pypdf": _FAKE_PYPDF}):
            with self.assertRaisesRegex(PdfPipelineError, "produced 3 pages; expected 4"):
                split_card_pdf_zip(b"3", ["E00", "N00"], pages_per_card=2)


if __name__ == "__main__":
    unittest.main()
