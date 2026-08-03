# TAG BOV Engine — Handoff

Upload this file at the top of a new chat. It carries the full state of the
project so nothing has to be re-derived.

---

## What this is

An assembly pipeline that produces Marcus & Millichap Broker Opinion of Value
books for The Anton Group. The corporate template is a 53-page InDesign
document. Most of it never changes between deals; a small core does. The
pipeline copies the unchanging pages, stamps images into a few, renders the
rest from data, and assembles a PDF.

**Do not use Claude Design for this.** These pages are already designed, by
M&M, in the IDML. The job is transcription to code with a measurable correct
answer. Design has no version control and no determinism, and it was the source
of the inconsistency this project exists to fix.

---

## Upload these to a new chat

| File | Why |
|---|---|
| `HANDOFF.md` | this file |
| `compile/bov_template_pack.json` | **replaces the 53-page PDF entirely** — carries all geometry, tokens, slots |
| `studio/tag_bov_studio.html` | the console, if UI work is planned |
| `manifests/*.yaml` | plate classification, multifamily and land |

**Do not re-upload the 53-page corporate PDF or the Albemarle PDF.** Each page
becomes an image in context and that is what exhausted the image budget. The
template pack contains everything those PDFs were needed for. Keep the PDFs on
disk for the assembler, which reads them at build time, not in conversation.

---

## Measured facts — all verified, do not re-derive

**Geometry.** Corporate template is 53 pages, uniform **792 × 612 pt**
(11 × 8.5 in landscape), 0.125 in bleed, origin top-left. 761 top-level frames
recovered from the IDML in page-local coordinates.

**Validation that the geometry is trustworthy:** the footer band reads
`[0, 578.79, 233.28, 595.13]` from the IDML and `x0:0, x1:233.3, top:578.8,
bottom:595.1` measured independently off the rendered PDF. Two unrelated
sources agreeing to 0.02 pt.

**Fonts.** Frank Ruhl Libre (display) and Roboto (UI). Both Google Fonts, both
free, both exact corporate matches. A MinionPro reference exists only in a dead
legacy footer layer — ignore it.

**Palette** (screen values measured off the rendered PDF; CMYK is from the
InDesign swatch book, in the pack):

    navy    #002B5C     orange      #F58026     grey band  #E5E7E6
    ink     #222222     orange warm #E5893F     grey mid   #A7A9AC

**Footer.** Page numbers are hardcoded into the artwork (`25 | INVESTMENT
OVERVIEW`). Any omitted section breaks every downstream number. The band sits
on flat grey with no artwork beneath, so it can be white-boxed and restamped.
This is what makes mix-and-match viable.

**Image slots.** 55 image frames resolve to six named slots. The IDML embeds
**zero** image payloads — all 55 are external links to a `Links` folder. Every
asset was recovered from the corporate PDF instead via `pdfimages`.

    divider_bg        8 frames, 1 unique asset, full-bleed 792x612
                      -> one file swap retones all 8 section dividers
    property_photo    24 frames, 11 distinct aspect ratios (0.588 - 2.121)
                      -> every upload needs a focal point or crops decapitate buildings
    advisor_headshot  1 frame, 4:5
    brand_logo / marketing_bg / corporate_stock   locked, corporate

**Page classification** (53 plates): 21 static · 3 annual · 6 variant ·
14 stamp · 9 build. Only `build` plates render; the rest are file copies or
copy-plus-image-stamp.

**Copy budget, plate 25.** Description and highlights share one frame,
349 × 371 pt, 26 lines at 14 pt leading. The corporate template uses **25 of
26**. Budget: description ~1,275 ch (1,360 hard max), highlights 4–6 bullets
at ~440 ch total. Two lines over and the frame overflows.

**Total per-property copy surface: ~1,600 characters.** Metro copy is written
once per market; advisor bios once per advisor. Everything else is tabular or
mechanical.

---

## Architecture

Four layers, in dependency order.

1. **Template pack** — `idml_compile.py` reads the IDML (a zip of XML, no Adobe
   needed) and emits `bov_template_pack.json`: tokens, slots, per-page frame
   geometry. Re-run whenever corporate reissues the template. Everything
   downstream reads only the pack.

2. **Page library** — the corporate PDF split into 53 single-page files.
   Byte-identical passthrough for static plates. Regenerate with:

       qpdf --empty --pages master_53.pdf 1-53 -- /dev/null   # verify first
       python3 -c "from pypdf import PdfReader,PdfWriter; r=PdfReader('master_53.pdf'); \
       [PdfWriter().add_page(p) or None for p in r.pages]"     # see repo notes

   Assemble with `qpdf --pages`, not pypdf — qpdf dedupes shared image objects
   (49 MB vs 63 MB on the same 37-page selection).

3. **Copy layer** — `copyfit.py`. Computes character budgets from frame
   geometry, builds a length-bounded generation prompt, and validates output:
   every numeral in generated copy must trace to the fact sheet, plus
   compliance phrase filters. Tested against real Albemarle copy — passes clean,
   catches a single corrupted figure (85,129 → 91,400).

4. **Assembler** — `assemble/assembler.py`. Consumes a config of the shape the
   console emits and writes a PDF. Four operations matching the four page
   classes: passthrough, stamp, build, footer restamp. Run it:

       python3 assemble/assembler.py examples/config_pricing_only.json \
               <page-library-dir> out.pdf fonts/

   **Renders with reportlab, not headless Chrome.** No browser is needed, which
   removes a deployment dependency. Absolute positioning against the pack's own
   frame boxes turned out to suit reportlab better than CSS would.

5. **Console** — `studio/tag_bov_studio.html`. Plate selection, presets, asset
   class, team roster, photo library with focal points and live crop previews,
   slot bindings, property intake, preflight. State persists via
   `window.storage`. **Wired to the assembler:** the Assemble button calls
   `buildConfig()` (state → the assembler's `{order, divider_texture}` contract)
   and POSTs it to the local build server, which returns the finished PDF. The
   page model is realigned to the template (Executive Summary + Anton Advantage
   inserts, Presented By dropped, mandatory-page locks). "Save as preset" persists
   named presets; "Download config" emits the raw config for CLI runs.

6. **Build server** — `serve/app.py` (FastAPI). `POST /api/bov/build` runs
   `assemble()` and streams back the PDF; `GET /api/health` reports library
   status. The Anthropic API key (ROADMAP Part D) will live only here, never in
   the browser. Run: `python -m uvicorn serve.app:app --port 8000`. Operator
   images resolve against `BOV_LIBRARY_ROOT`; unresolved paths fall back to the
   corporate placeholder so a build never crashes on a missing file.

---

## Assembler status — verified end to end

A 19-page "Pricing only" book assembles and renders correctly, 37 MB.

**Plate 25 has been built and diffed against the corporate original.** After
four measured corrections, every landmark matches exactly:

    landmark     corporate                    built                        delta
    head         (36.0, 68.7)  FRL-Regular    (36.0, 68.7)  FRL-Regular    0.0
    desc_head    (36.0, 127.9) FRL-Bold       (36.0, 127.9) FRL-Bold       0.0
    offer_head   (411.2, 335.1) FRL-Bold      (411.2, 335.1) FRL-Bold      0.0
    rules        [89.7, 349.0, 369.1, 389.3]  [89.7, 349.0, 369.1, 389.3]  exact

The corrections, all now constants in `build_plate25`: header baseline was
4.6 pt low, description head 2.3 pt high, offering summary needed a 4 pt left
inset and sat 8.1 pt high, and the table row pitch was 20.5 rather than the
corporate 20.15. **Compiled geometry reproduces corporate layout.** That was
the load-bearing assumption of the whole project and it holds.

Residual pixel diff is ~16 %, concentrated in two places, neither a defect:

- **Body copy** — InDesign's paragraph composer breaks lines differently than a
  greedy wrap. Matching it exactly would mean implementing Knuth-Plass. The
  measure, leading and baselines are right; only the break points differ.
- **Hero photo** — a different crop of the same source. Focal point choice, not
  a positioning error. The frame edges align.

> **Status update (2026-08-03):** six of the seven data-driven multifamily
> builders now exist and are diffed against corporate — 25, 35, 41, 37/38,
> 44/45. Only cover (1) and TOC (4) remain. See `ROADMAP.md` for current
> state and `CLAUDE.md` for the technical architecture and the measure/build/
> correct method. The notes below are the original brief, kept for context.

### Known limitations, in priority order

1. **Cover (1) and TOC (4) still lack builders.** They fall back to the
   corporate placeholder and log `build:NO-BUILDER`. Plates 25, 35, 37, 38, 41,
   44, 45 are built. The output is an honest hybrid until the last two land.
2. **Superseded footer text stays in the content stream.** The grey band covers
   the old page number visually — renders correctly at 288 dpi, verified — but
   the original text objects survive, so extracting or searching the PDF returns
   both the old and new numbers. Fine for a proof, sloppy for something sent to
   an owner. Fix requires content-stream surgery to drop the old text operators.
3. **File size.** Stamping over a corporate page leaves the original image
   embedded underneath. 19 pages runs 37 MB. Encoding stamps as progressive
   JPEG at 200 dpi took it down from 127 MB; going lower means removing the
   buried originals.
4. **Roboto is missing.** Not needed by any plate built so far.

## Asset class is a plate set, not an image swap

Discovered when 2202 Albemarle Road (a vacant development site) was mapped
against the template. The corporate plate 25 offering summary is
`Listing Price · NOI · Cap Rate · GRM · Total Return % · Price/SF · Rent/SF ·
Price/Unit`. A land deal has `List Price · Lot Area · Zoning · FAR · Buildable
SF · $/BSF · Delivery`. **Overlap: Listing Price only.** All seven Rent
Comparables plates are meaningless.

Of the Albemarle draft's 19 pages: 10 reuse corporate plates unchanged, 5 need
land variants, 4 have no corporate equivalent (executive summary, zoning
pathways, strategies reconciled, team select experience).

So the console's asset-class selector must switch the **core plate set** —
multifamily core, land core, retail core — while boilerplate, dividers, bios
and front matter stay shared. See `manifests/land_plate_manifest.yaml`.

---

## Decisions already made

- **No InDesign.** Nobody on the team has a seat and the goal is not to need
  one. Static pages come from the PDF library; variant plates get rebuilt as
  HTML using the compiled geometry. Adds ~4 templates, no structural change.
- **HTML/CSS → PDF via headless Chrome** at 792 × 612 pt for all built plates.
  Load Frank Ruhl Libre and Roboto explicitly — the Albemarle draft fell back
  to DejaVu/Liberation because they weren't installed.
- **Pre-render finite combinatorics.** 8 dividers × 6 asset classes = 48 plates
  baked once. Metro trio per market. Bio/cover/back per advisor. Nothing that
  varies per property should be *designed* at generation time.
- **The model rewrites, it does not author.** Inputs are a structured fact
  sheet plus the broker's rough notes carrying the thesis. It converts those to
  house-voice prose at a measured length. It never originates the investment
  case and never states a number absent from the facts.
- **House voice from prior BOVs**, not from a style prompt. Extract description
  sections from 10–15 closed deals as few-shot examples.
- **The zoning-counsel disclosure on land plate L04 is hard-coded**, never
  generated. It backs a $16.0M ask against a $5.4M floor.

---

## Open questions

1. **Is landscape mandatory for land BOVs?** The Albemarle draft is portrait
   8.5 × 11; corporate is landscape. The zoning table and transit list are
   built tall. Landscape is genuinely the worse format for dense tabular
   zoning analysis.
2. **What stack is the dashboard on?** The console should become a route in
   Nelson's app at dashboard.aipropertyintelligence.com, not a standalone file.
   Proposed contract:

       POST /api/bov/requests  { property_id, preset, asset_class, advisors[],
                                 comps:{sale:[],rent:[]}, overrides } -> {request_id}
       GET  /api/bov/requests/:id -> { status, pages, pdf_url, warnings[] }

3. **Central asset storage.** A browser cannot re-read local disk between
   sessions. The library stores previews, focal points and paths; full-res
   originals need somewhere the build worker can reach.
4. **Divider imagery licensing.** The existing divider is licensed Getty. New
   asset-class images need their own clearance.

---

## Next steps, in order

1. ~~Render plate 25 and diff it against the corporate original.~~ **Done.**
   Landmarks match exactly.
2. ~~Wire a real assembler.~~ **Done.** 19-page book assembles.
3. **Build the remaining seven multifamily builders** — plates 1, 4, 35, 37, 38,
   41, 44/45. Plate 25 established the pattern: read the frame box from the
   pack, draw at those coordinates, diff, fold the measured offsets back in as
   constants. Budget an hour or two per plate, less as the shared helpers firm
   up.
4. **Strip superseded footer text** rather than covering it (limitation 2).
5. **Divider template + two asset-class images.** Cheapest proof of the overlay
   swap.
6. ~~Wire the console's Assemble button to the assembler.~~ **Done.** Config
   bridge (`buildConfig()`) + local build server (`serve/app.py`); verified end
   to end — browser POST → PDF, footers renumbered, 0 NO-BUILDER gaps.
6b. ~~Preloaded asset catalog + full team wiring.~~ **Done.** Licensed imagery is
   committed under `assemble/assets/stock/` and catalogued by
   `tools/build_asset_catalog.py` → `asset_catalog.json`; the server serves the
   console + `/assets` + `/api/assets` + `/api/team`. The console preloads the
   catalog (no upload needed), auto-binds slots, rebinds the divider per asset
   class, and seeds the four full-package advisors (headshots + bios) from the
   dataset. Verified: divider background and advisor bio render with real imagery.
7. **LLM copy generation (ROADMAP Part D, high-priority MVP).** Wrap
   `copy/copyfit.py` with a single `anthropic` call in the build server:
   generate → `check()` → regenerate once. Haiku 4.5 default, Sonnet 5 for the
   Executive Summary; model as a per-page config knob. Extend `copyfit.py`
   budgets to the exec-summary body and advisor bio (plate 25 only today).
8. **Build the land core** against Albemarle using the land manifest.
9. Metro library, dashboard integration. Install qpdf on PATH so built PDFs are
   compressed (currently ~55 MB uncompressed; assembler falls back when qpdf is
   absent).

---

## Repo layout

    tag-bov-engine/
      HANDOFF.md                          this file
      studio/tag_bov_studio.html          the console
      compile/idml_compile.py             IDML -> template pack
      compile/bov_template_pack.json      compiled output (upload this, not the PDF)
      copy/copyfit.py                     budgets, prompt contract, validator
      manifests/bov_page_manifest.yaml    multifamily, 53 plates classified
      manifests/land_plate_manifest.yaml  development-site plate set
      notes/albemarle_mapping.py          the 19-page mapping analysis
      notes/albemarle_validate.py         validator run against real copy

Not included, regenerate or keep locally: the 53-page corporate PDF, the split
page library (79 MB), the 61 extracted image assets, the unpacked IDML.
