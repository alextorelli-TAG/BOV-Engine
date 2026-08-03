# TAG BOV Engine

An assembly pipeline that produces **Marcus & Millichap Broker Opinion of Value
(BOV) books** for The Anton Group — consistently, on demand, and pixel-faithful
to the corporate InDesign template, without needing InDesign.

## What problem this solves

The corporate BOV template is a 53-page InDesign document. Most of its pages
never change from deal to deal; a small core does. Historically each book was
produced by hand in a design tool, which was slow and drifted out of spec —
fonts, spacing, and numbers came out slightly different every time.

This engine fixes that. It treats the template as **data**: it copies the pages
that never change, stamps images into the ones that only need a photo, and
**rebuilds the data-driven pages from measured coordinates** so every book comes
out identical to the corporate standard. The result is a print-ready PDF.

## What you can do with it

- **Pick what goes in the book.** Choose a preset (e.g. *Full*, *Lean*,
  *Repeat client*) or an individual set of sections.
- **Pick the deal type.** Multifamily today; land and retail are on the roadmap.
  The deal type swaps in the right core pages (a land deal has different
  offering metrics and comps than a multifamily deal).
- **Drop in the deal specifics.** Property facts, offering summary, sale and rent
  comparables, advisor bios, and the property photos.
- **Get a finished PDF** that matches the corporate template exactly, with
  correct page numbers and section footers throughout.

## What works today (prototype)

- The corporate template has been fully measured and compiled into a portable
  "template pack" (all geometry, colors, fonts, and image slots).
- The **assembler** produces a real multi-page PDF from a job description.
- **Data-driven page builders** that reproduce the corporate layout exactly
  (verified to a fraction of a point against the original):
  - Property Summary (offering summary + description + highlights)
  - Sale Comps Summary and Rent Comps Summary tables
  - Sale Comps Detail and Rent Comps Charts (two comps per page, with photos,
    unit-mix tables, and stat icons)
- The **operator console** (`studio/tag_bov_studio.html`) for choosing pages,
  presets, advisors, photos (with focal points and live crop previews), and
  property intake.

See [ROADMAP.md](ROADMAP.md) for what's next and [CLAUDE.md](CLAUDE.md) for the
technical architecture.

## Running it

You need Python 3.12+, a few packages, and `qpdf`. On Windows:

```bash
pip install reportlab pypdf pillow pyyaml pdfplumber pymupdf
winget install QPDF.QPDF
```

The pipeline reads the corporate pages at build time but they are **not stored
in this repo** (they're proprietary and large). Restore them locally once:

1. Put the corporate master PDF somewhere on disk.
2. Split it into the page library:

   ```bash
   python tools/split_library.py "<path to corporate master.pdf>"
   ```

Then assemble a book from a job config:

```bash
python assemble/assembler.py examples/config_pricing_only.json page_library out.pdf fonts/
```

To preview and verify a single page against the corporate original:

```bash
python tools/diff_plate.py examples/config_plate35_only.json 35 --show
```

## Running the console + build server

The operator console is served by a small local server that also runs the
assembler and streams the finished PDF back. Start it once:

```bash
pip install -r serve/requirements.txt
python -m uvicorn serve.app:app --port 8000
```

Then open **http://localhost:8000** in a browser. Configure the book and click
**Assemble PDF** — the console POSTs its config to the server and downloads the
result. (If you open the raw `studio/tag_bov_studio.html` file instead, Assemble
still works but preloaded assets won't load and it falls back to downloading the
config JSON for a CLI run.)

### Preloaded asset catalog

Licensed imagery lives in the repo (this is an internal-only tool) and shows up in
the console as point-and-click thumbnails — no per-build upload. Drop images into
`assemble/assets/stock/` — `dividers/<assetclass>/` for section backgrounds,
`corporate/` for the InDesign `Links` set, `textures/` for grounds — then rebuild
the catalog:

```bash
python tools/build_asset_catalog.py
```

This writes `assemble/assets/asset_catalog.json`, which the server exposes at
`GET /api/assets`. The team roster comes from `examples/team_the_anton_group.json`
via `GET /api/team`. Operator property photos are still uploaded per deal (Photos
tab) and resolved, along with the catalog, against `BOV_LIBRARY_ROOT`:

```bash
BOV_LIBRARY_ROOT="<path to your images>" python -m uvicorn serve.app:app --port 8000
```

## Repository layout

| Path | What it is |
|---|---|
| `assemble/` | The assembler and the page builders (the heart of the engine) |
| `compile/` | Reads the corporate InDesign file and produces the template pack |
| `copy/` | Character-budget and copy-validation logic for generated prose |
| `manifests/` | Which pages exist and how each is produced, per deal type |
| `studio/` | The operator console (single-page web app) |
| `serve/` | Local build server the console POSTs to (FastAPI) |
| `tools/` | Developer utilities for measuring and verifying pages |
| `examples/` | Sample job configs |
| `fonts/` | Frank Ruhl Libre + Roboto (free Google Fonts, exact corporate match) |

## A note on the corporate assets

The corporate InDesign package, the split page library, and the licensed Getty
imagery are intentionally **kept out of version control**. This repo carries the
*code* and the *compiled geometry* — everything needed to rebuild a book once the
corporate source is present locally.
