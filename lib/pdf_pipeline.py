"""Browser-first HTML to PDF rendering with an optional CMYK post-process.

The HTML document is deliberately rendered as ordinary browser-safe RGB/CSS.
That keeps the Streamlit preview and the PDF source identical. CMYK conversion
happens after layout, through Ghostscript's vector-preserving ``pdfwrite``
device, so print color policy does not create a second geometry implementation.

Playwright is optional. When it is installed and Chromium is available, it is
used first because it shares the browser layout model with the Streamlit
preview. WeasyPrint remains a controlled fallback for deployments that cannot
ship Chromium.
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Sequence


class PdfPipelineError(RuntimeError):
    """Raised when PDF rendering or CMYK conversion cannot complete."""


class PdfRendererUnavailable(PdfPipelineError):
    """Raised when an optional PDF renderer is not installed or runnable."""


def _ghostscript_binary() -> Optional[str]:
    """Return the first supported Ghostscript executable on the PATH."""
    for name in ("gs", "gswin64c", "gswin32c"):
        binary = shutil.which(name)
        if binary:
            return binary
    return None


def _chromium_binary() -> Optional[str]:
    """Return a system Chromium path when the deployment provides one."""
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        binary = shutil.which(name)
        if binary:
            return binary
    return None


def _render_with_playwright(html: str) -> bytes:
    """Render HTML with Chromium's print engine, preserving browser layout."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on deployment extras
        raise PdfRendererUnavailable("Playwright is not installed") from exc

    try:
        with sync_playwright() as playwright:
            launch_options = {"headless": True}
            system_chromium = _chromium_binary()
            if system_chromium:
                launch_options["executable_path"] = system_chromium
            browser = playwright.chromium.launch(**launch_options)
            try:
                page = browser.new_page(device_scale_factor=1)
                page.set_content(html, wait_until="load")
                # Do not export before web fonts have settled. This is harmless
                # for deployments that use only local/system fonts.
                page.evaluate(
                    """() => document.fonts && document.fonts.ready
                        ? document.fonts.ready
                        : Promise.resolve()"""
                )
                return page.pdf(
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
            finally:
                browser.close()
    except PlaywrightError as exc:  # pragma: no cover - depends on deployment
        raise PdfRendererUnavailable(f"Chromium PDF rendering failed: {exc}") from exc


def _render_with_weasyprint(html: str) -> bytes:
    """Render HTML with the existing server-side fallback."""
    try:
        from weasyprint import HTML
    except ImportError as exc:  # pragma: no cover - depends on deployment extras
        raise PdfRendererUnavailable("WeasyPrint is not installed") from exc

    return HTML(string=html).write_pdf()


def _render_pdf(html: str, renderer: str) -> bytes:
    if renderer == "browser":
        return _render_with_playwright(html)
    if renderer == "weasyprint":
        return _render_with_weasyprint(html)
    if renderer != "auto":
        raise ValueError(f"Unsupported PDF renderer: {renderer}")

    try:
        return _render_with_playwright(html)
    except PdfRendererUnavailable:
        return _render_with_weasyprint(html)


def _ghostscript_command(
    binary: str,
    source: Path,
    destination: Path,
    profile_path: Optional[Path],
) -> Sequence[str]:
    """Build a vector-preserving RGB-to-CMYK Ghostscript command."""
    command = [
        binary,
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=/prepress",
        "-dProcessColorModel=/DeviceCMYK",
        "-sColorConversionStrategy=CMYK",
        "-sColorConversionStrategyForImages=CMYK",
        "-dDeviceGrayToK=true",
        "-dAutoRotatePages=/None",
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=true",
        f"-sOutputFile={destination}",
    ]
    if profile_path is not None:
        # Ghostscript uses this profile for color-managed output where the
        # selected version/device supports it. Plain CMYK conversion remains
        # valid without a profile; PDF/X output-intent authoring is a separate
        # concern and should not be guessed here.
        command.extend(["-dOverrideICC=true", f"-sOutputICCProfile={profile_path}"])
    command.append(str(source))
    return command


def convert_pdf_bytes_to_cmyk(
    pdf_bytes: bytes,
    *,
    profile_path: Optional[str] = None,
) -> bytes:
    """Convert a rendered PDF to DeviceCMYK without rasterizing the page.

    ``profile_path`` may point to the print shop's ICC profile. If omitted,
    Ghostscript performs a standard CMYK conversion. The process is kept in a
    temporary directory and the profile path is passed as an argument, never
    copied into the generated PDF source tree.
    """
    if not pdf_bytes:
        raise PdfPipelineError("Cannot convert an empty PDF")

    binary = _ghostscript_binary()
    if binary is None:
        raise PdfPipelineError(
            "CMYK export requires Ghostscript (install the ghostscript system package)"
        )

    resolved_profile: Optional[Path] = None
    if profile_path:
        resolved_profile = Path(profile_path).expanduser()
        if not resolved_profile.is_file():
            raise PdfPipelineError(f"CMYK ICC profile not found: {resolved_profile}")

    with tempfile.TemporaryDirectory(prefix="phacker-pdf-") as temp_dir:
        temp_root = Path(temp_dir)
        source = temp_root / "source.pdf"
        destination = temp_root / "output-cmyk.pdf"
        source.write_bytes(pdf_bytes)
        command = _ghostscript_command(binary, source, destination, resolved_profile)
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0 or not destination.is_file():
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise PdfPipelineError(
                "Ghostscript CMYK conversion failed"
                + (f": {detail[-1200:]}" if detail else "")
            )
        return destination.read_bytes()


def build_pdf_bytes(
    html: str,
    *,
    renderer: str = "auto",
    use_cmyk: bool = True,
    profile_path: Optional[str] = None,
) -> bytes:
    """Render one canonical HTML document, then optionally convert its colors."""
    raw_pdf = _render_pdf(html, renderer)
    if not use_cmyk:
        return raw_pdf

    selected_profile = profile_path or os.environ.get("PHACKER_CMYK_PROFILE")
    return convert_pdf_bytes_to_cmyk(raw_pdf, profile_path=selected_profile)


def _safe_pdf_stem(card_id: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", card_id.lower()).strip("-")
    return stem or "card"


def split_card_pdf_zip(
    pdf_bytes: bytes,
    card_ids: Sequence[str],
    *,
    pages_per_card: int,
) -> bytes:
    """Split one batch PDF into a ZIP containing one vector PDF per card."""
    if pages_per_card not in {1, 2}:
        raise ValueError("pages_per_card must be 1 or 2")
    if not card_ids:
        raise ValueError("At least one card ID is required")

    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise PdfRendererUnavailable("Individual PDF export requires pypdf") from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    expected_pages = len(card_ids) * pages_per_card
    if len(reader.pages) != expected_pages:
        raise PdfPipelineError(
            f"Individual PDF batch produced {len(reader.pages)} pages; expected {expected_pages}"
        )

    archive_buffer = io.BytesIO()
    manifest_cards = []
    used_stems: dict[str, int] = {}
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for card_index, card_id in enumerate(card_ids):
            base_stem = _safe_pdf_stem(card_id)
            duplicate_index = used_stems.get(base_stem, 0) + 1
            used_stems[base_stem] = duplicate_index
            stem = base_stem if duplicate_index == 1 else f"{base_stem}-{duplicate_index}"
            filename = f"{stem}.pdf"

            writer = PdfWriter()
            first_page = card_index * pages_per_card
            for page_index in range(first_page, first_page + pages_per_card):
                writer.add_page(reader.pages[page_index])
            pdf_buffer = io.BytesIO()
            writer.write(pdf_buffer)
            archive.writestr(filename, pdf_buffer.getvalue())
            manifest_cards.append({
                "card_id": card_id,
                "filename": filename,
                "pages": pages_per_card,
            })

        archive.writestr(
            "manifest.json",
            json.dumps({
                "schema_version": 1,
                "pages_per_card": pages_per_card,
                "cards": manifest_cards,
            }, indent=2) + "\n",
        )
    return archive_buffer.getvalue()


def build_individual_pdf_zip(
    html: str,
    card_ids: Sequence[str],
    *,
    include_back_pages: bool,
    renderer: str = "auto",
    use_cmyk: bool = True,
    profile_path: Optional[str] = None,
) -> bytes:
    """Render once, then split into one PDF per card to avoid N browser launches."""
    batch_pdf = build_pdf_bytes(
        html,
        renderer=renderer,
        use_cmyk=use_cmyk,
        profile_path=profile_path,
    )
    return split_card_pdf_zip(
        batch_pdf,
        card_ids,
        pages_per_card=2 if include_back_pages else 1,
    )
