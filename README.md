# P-Hacker Card Tweaker

One Streamlit pipeline for P-Hacker's evidence-card art:

1. **Tune** every chart type's shape/hatch/ink params and the real card
   composite (band %, chart opacity, color wash) against the *actual* look
   shipped in the game — not an approximation.
2. **Preview** the result through the exact same HTML/CSS template that also
   drives the PDF, so what you see is what prints.
3. **Build dice glyphs** from the same chart family: six independently selectable,
   distance-readable SVG faces with contour-only rendering, optional blue/gray
   finding ink, and a configurable die background.
4. **Export** a YAML config to back up into `gquinche/phacker-game` (branch
   `experiment/simplified-ui` as of 2026-07 — that's where the SVG migration,
   `bake_card_svgs.py`, and `phacker_cards.ipynb` actually live; `trunk` is
   stale for card art), a six-face SVG ZIP, and three print-ready **CMYK** PDF
   modes: a grid atlas, one combined one-card-per-page document, or a ZIP with
   one front-only or front-and-back PDF file per card.

## Architecture

```
app.py                 entry point — st.navigation/st.Page, shared sidebar (YAML import/export)
pages/
  chart_lab.py          per-chart-type tuning with ordinary keyed Streamlit widgets
  dice_svg.py           six configurable minimal SVG die faces + preview/downloads
  ink_lab.py            per-page CMYK recipes, C/K plane, policies, and histogram
  card_preview.py        full gallery, every chart type × both findings, at real card size
  print_atlas.py         page/grid/bleed config, live atlas preview, "Generate PDF" (browser-first)
  config_page.py          YAML dump, reset, notes on where each value maps in phacker-game
lib/
  chart_generators.py    the 11 chart-art generators (bar, scatter×2, gaussian, box, gap,
                          synthetic_control, forest, km_curve, did_parallel_trends, event_study) —
                          ported from tools/card-art/fake_charts_cardart.py
  chart_params.py         per-chart tunable-param schemas (every chart, not just
                          synthetic_control) — this is what pages/chart_lab.py renders controls from
  dice_render.py          contour-only chart reduction, die-face SVGs, preview, and ZIP packaging
  card_render.py          THE single card/atlas HTML+CSS template shared by preview and PDF
  card_back_render.py     simplified-ui card backs from real SVG motifs, one shared layout
  pdf_pipeline.py         browser-first PDF + Ghostscript CMYK + vector-safe per-card ZIP splitting
  config_io.py            YAML load/save/merge, page-size table
  editor_state.py          keyed widget values -> render/export config snapshot
  ink_control.py           page recipes, histogram + foreign-ink audit
  ck_picker.py             bidirectional JS Canvas + browser color picker component
  paper.py                 one shared front/back paper-stock palette (white default)
  colors.py                CMYK <-> hex helpers
  pseudo_stats.py           deterministic n=/p= footer text (mirrors cardPseudoStats.ts)
assets/card_backs/       real SVG motifs copied from phacker-game experiment/simplified-ui
config_defaults.yaml     starting values — `palette`/`hatch` keys mirror the real repo's dicts;
                          `chart_params` is this tool's own addition, see below
requirements.txt
packages.txt              system packages Streamlit Community Cloud installs for PDF rendering
```

### Why one template for preview *and* print

Earlier versions of this tool had three different implementations of "what a
card looks like" (a rough PIL composite for the on-screen preview, a
separate matplotlib-patches redraw for the PDF, and neither matching the
game's actual CSS) — so tuning a value in the preview told you nothing
reliable about the print output. `lib/card_render.py` now renders **one**
HTML/CSS card (`.tw-card`, deliberately named to echo the real
`.print-card` family in `src/styles/game-cards.css`) and `print_atlas.py` passes
the exact same HTML string to the live browser preview and the PDF pipeline.

The default PDF renderer is browser-first: Playwright/Chromium uses the same
layout engine family as the preview. WeasyPrint remains an explicit fallback
for deployments that cannot ship Chromium. The fallback is still fed the same
HTML, but it is not treated as a second design implementation.

The HTML intentionally stays browser-safe RGB. Python runs an optional
Ghostscript `pdfwrite` post-process after layout, converting the finished PDF
to DeviceCMYK with the selected ICC profile while keeping text and vector
content wherever the PDF engine permits. This separates geometry from print
color decisions: a small CMYK conversion difference is acceptable, but a card
moving or resizing between preview and export is not.

Screen-only atmosphere — shadows, warm paper texture, warm crease tint, and
sheet presentation — is isolated in `@media screen` and exposed as config
flags. It can be tuned without changing the print boxes or the print ink audit.

### Real simplified-UI card backs

The Card Back selector renders the actual motif assets from `gquinche/phacker-game`
branch `experiment/simplified-ui`: stripe, chevron, argyle, hex lattice, scallop,
contour, flow, and the experimental guilloche. `lib/card_back_render.py` uses the
same exact dimensions and selected paper-stock color as the front (white by default),
then applies the engraved frame, motif, and approved B/W `P` / `DEPARTMENT OF
REPRODUCIBILITY` bureau seal from the attached print prototype. Card Preview can
replace P with I–V for reviewing the in-game proposal, but physical preview/PDF backs
intentionally contain no Roman numeral or card ID, so every back is identical and
reveals no deck information. Print Atlas can append one matching back sheet per
front sheet for browser preview and PDF output.

All motifs except guilloche are **Hero Patterns by Steve Schoger (CC BY 4.0)**.
Guilloche was authored for P-Hacker. See `assets/card_backs/README.md`.

### Physical corner finishing

Print Atlas defaults to **square corners** on fronts and backs so every cut is a straight
guillotine line. Rounded print geometry is optional, with a configurable millimetre radius;
otherwise use a physical corner cutter after trimming. Game-size Card Preview remains rounded.

### Ink Lab and strict print preflight

Ink Lab owns separate EFFECT, NO EFFECT, and BACK CMYK recipes. It provides exact
C/M/Y/K sliders, allowed-channel policies, a real JavaScript Canvas Cyan-versus-Black
picker plus native browser color input (Streamlit components v2), and a faceted
channel-coverage histogram. Print Atlas audits the canonical HTML before export;
when strict preflight is enabled, any color that activates a channel outside that
page's policy blocks PDF generation. Screen-only `@media screen` colors are
excluded from the print audit. Defaults are EFFECT=C/M/K, NO EFFECT=K, and BACK=K,
with Y=0 on all pages.

The CMYK sliders are the print recipe and the preview source colors are derived
from them. The PDF post-process can use a print-shop ICC profile via
`print.cmyk_profile_path` or `PHACKER_CMYK_PROFILE`. With no profile, Ghostscript
uses its standard CMYK conversion. This intentionally allows a small visual
conversion difference while preserving the strict channel policy and avoiding a
second layout implementation.

### PDF engines and CMYK post-processing

`lib/pdf_pipeline.py` tries Playwright/Chromium first in `auto` mode, using
`page.pdf(print_background=True, prefer_css_page_size=True)` so CSS page size,
bleed, and backgrounds are honored by a browser-grade print engine. If the
browser renderer is unavailable, `auto` falls back to WeasyPrint; selecting
`browser` or `weasyprint` makes the choice explicit.

After HTML-to-PDF layout, Ghostscript's vector `pdfwrite` device performs the
optional RGB-to-CMYK conversion. This is deliberately not `html2pdf.js`: that
library's documented pipeline goes through html2canvas and jsPDF, which turns the
page into a raster image and is a poor fit for print-ready selectable text and
SVG. The CMYK step is also not a generic promise that every PDF construct stays
vector — transparency, gradients, and unusual SVG effects should be checked in
preflight — so the atlas keeps print CSS restrained.

Print Atlas offers three explicit modes. The default grid atlas places several
cards per print sheet. The one-card-per-page mode produces one combined document
with every front on its own page and, when enabled, its matching back immediately
after it. The separate-files mode takes that same card-sized batch, applies the
same optional CMYK pass once, then uses `pypdf` to split it into a ZIP without
rasterizing it or launching Chromium for every card. Each split PDF is front-only
or has its back on page 2, and a manifest records the exact filenames and page
count.

`st.components.v2.component` is useful if we later want a browser button to emit
raw PDF bytes back to Python, but it is not required for the server-side PDF
button. A component can communicate Blob/base64 state; it cannot itself make the
browser's native print dialog return a PDF file. The current implementation keeps
the simpler server-side flow and uses the component system only for existing
interactive controls.

### PRECOLOR — matches the real repo's own stated direction

The real `tools/card-art/phacker_cards.ipynb` (generated by `build_nb.py`)
documents two modes:

- `PRECOLOR = True` (**recommended**, and the default here) — bake the
  finding hex directly into the SVG. No runtime work.
- `PRECOLOR = False` — ship `currentColor`-templated SVGs, recolor at
  runtime via the game's `useColoredSvg` hook. The notebook's own words:
  *"the complexity we're trying to retire."*

`lib.chart_generators.render_svg()` always renders with the real hex baked
in (matching what's actually shipped in `public/cards/*.svg` today). The
canonical HTML keeps those baked SVG colors unchanged; the browser PDF is
converted after layout by the Python/Ghostscript pipeline. The old
`recolor_svg_to_currentcolor()` helper remains available for experiments, but
it is no longer part of the export path.

### Dice SVG generator

Dice SVG reuses the 11 existing matplotlib generators, then applies a separate
small-scale reduction pass: axis furniture, labels, legends, grids, hatches,
area fills, and faint decorative clouds are removed; the remaining paths and
markers become heavier contour strokes inside a rounded 256 × 256 die face.
This leaves the card-art pipeline untouched while giving the physical die (and a
future ladder-of-credibility UI) a vocabulary that remains recognizable from
across the table.

The recommended six use distinct silhouettes: Gaussian curves, box-and-whisker,
bar, step curves, forest, and parallel-trends. They are only defaults: every
face selector can use any registered chart, choose EFFECT or NO EFFECT geometry, and set its
own deterministic seed. Colored outlines reuse the live Ink Lab blue/gray
palette; disabling them switches every face to one neutral dark contour.
Transparent SVG backgrounds are enabled by default for importing the contours
into Orca as texture artwork: both the fill and die frame are omitted, leaving
only the graph. Uncheck transparency to bake the independently configurable,
borderless background color instead. The `Fill around graphics (negative space)`
checkbox fills the area around each chart with its finding ink and redraws the
chart in the die background color; the SVG root and manifest record the boolean
`negative_space` choice. Export produces six standalone SVGs and a JSON manifest
in one ZIP, with individual SVG downloads available too.

### Chart registry — 11 types, every one tunable

The real repo's `fake_charts_cardart.py` dropped `km_curve` (Kaplan-Meier)
2026-07-09 as "reads as medical-specific, not general science texture" — but
that's a tuning problem, not a reason to drop the chart type, so it's
restored here (`lib/chart_generators.gen_km_curve`) with its decline-rate
ranges and resolution fully exposed in Chart Lab. More generally: every
chart type used to hardcode its sample sizes / effect-size ranges / noise
levels as Python literals, so only `synthetic_control` (via the old `syn`
dict) could be dialed in from the UI at all. `lib/chart_params.py` now gives
every chart type the same treatment — that's the actual fix for "this chart
doesn't look decent," not dropping it.

`gap_chart` and `synthetic_control` draw their primary line in the `ink`
parameter unconditionally (for both findings) — that's simply "use whatever
color is actually configured for this finding," not a hardcoded gray
constant that would silently ignore a palette change. It's not a
pixel-content requirement on the rendered SVG, and a chart mixing that ink
with a separate fixed decorative gray (e.g. `synthetic_control`'s placebo
cloud, which is meant to look muted regardless of finding) is completely
fine — see the color-rule note in `lib/chart_generators.py`'s module
docstring.

## Local setup

```bash
pip install -r requirements.txt
```

The browser-first renderer needs Playwright plus a Chromium executable, and
CMYK export needs Ghostscript. The WeasyPrint fallback also needs system
libraries (Pango/Cairo/GDK-Pixbuf). Locally:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

- **macOS**: `brew install ghostscript pango cairo gdk-pixbuf libffi`
- **Debian/Ubuntu**: `sudo apt-get install ghostscript chromium libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info` (package names vary by release)
- **Windows**: install Ghostscript and see [WeasyPrint's install docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows) for the fallback GTK3 runtime.

If Chromium is unavailable, choose Auto or WeasyPrint and the app uses the
fallback. If Ghostscript is unavailable, switch off CMYK export for a layout
proof; the button surfaces a clear error instead of crashing the app.

```bash
streamlit run app.py
```

## Syncing back to phacker-game

This tool never writes into `phacker-game` directly — export the YAML
(sidebar, any page) and copy values by hand into:

- `tools/card-art/fake_charts_cardart.py`'s `HATCH` module dict, or the
  notebook's tweak cell (`fc.HATCH.update(...)`).
- The notebook's `PALETTE` dict + `bake_card_svgs.py`'s `SIG`/`NULL`
  constants.
- `src/styles/game-cards.css` for `band_pct` / chart opacity / wash alpha,
  if you change those from the shipped defaults.
- `chart_params` (every non-hatch/non-`syn` number in every chart function)
  has **no existing counterpart in phacker-game** — those were hardcoded
  literals there. If a tuned value is worth keeping, hand-edit the matching
  literal in the chart's function body in `fake_charts_cardart.py`; there's
  no dict to paste into yet. Worth raising with whoever owns that file if
  you find yourself doing this a lot — it'd be a small refactor to make it
  read a params dict the same way this tool does.

Re-run the notebook's bake + parity-test cells after pasting values in, same
as always.
