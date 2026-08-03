# CLAUDE.md

Guidance for AI agents working in this repo. Read this before editing.

## What this is

A pipeline that assembles Marcus & Millichap BOV books for The Anton Group by
**transcribing the corporate InDesign template into code**, not by re-designing
it. Every built page has a measurable correct answer: the corresponding page in
the corporate PDF. **Do not use design tools or generative layout here** — match
the corporate geometry exactly and verify with the diff loop below.

## Architecture — four layers (dependency order)

1. **Template pack** — `compile/idml_compile.py` reads the corporate `.idml`
   (a zip of XML; no Adobe needed) and emits `bov_template_pack.json`: page
   size, tokens (colors/type/footer), per-page text-frame geometry, and image
   slots. Re-run only when corporate reissues the template. **A byte-identical
   copy of the pack lives in `compile/`, `assemble/`, and `copy/`** — the
   assembler reads `assemble/bov_template_pack.json`. Keep them in sync.
2. **Page library** — the corporate master PDF split into `page_library/p01.pdf`
   .. `p53.pdf`. Byte-identical passthrough source for static pages. Regenerate
   with `tools/split_library.py`. Git-ignored (proprietary, ~79 MB).
3. **Copy layer** — `copy/copyfit.py`: character budgets from frame geometry,
   a length-bounded generation prompt, and a validator (every numeral in copy
   must trace to the fact sheet; compliance-phrase filters).
4. **Assembler** — `assemble/assembler.py`: consumes a job config and writes a
   PDF. Renders with **reportlab** (no headless browser). Four operations match
   the four page classes: `passthrough`, `stamp`, `build`, footer `restamp`.

Plus the **console** (`studio/tag_bov_studio.html`): the operator UI. Its
Assemble button is **not yet wired** to the assembler.

## Directory map

```
assemble/assembler.py      the assembler + all page builders  <- main file
assemble/bov_template_pack.json   compiled geometry the assembler reads
assemble/assets/           extracted brand pictograms (plate 44 stat icons)
compile/idml_compile.py    IDML -> template pack
copy/copyfit.py            copy budgets, prompt contract, validator
manifests/bov_page_manifest.yaml   53 plates classified (multifamily)
manifests/land_plate_manifest.yaml development-site plate set
studio/tag_bov_studio.html the operator console
tools/                     dev utilities (see below)
examples/config_*.json     sample job configs (per-plate + presets)
fonts/                     Frank Ruhl Libre (display) + Roboto (UI), OFL
notes/                     Albemarle land-deal mapping analysis
HANDOFF.md                 original project brief / decisions log
page_library/              (git-ignored) split corporate pages
YE 2025 BOV Template*/     (git-ignored) corporate IDML/PDF/INDD/Links
```

## The assembler in detail

- **Coordinates.** The pack and every builder use **points, origin top-left, y
  down**. reportlab is bottom-left, so `ry(y)` flips it and every draw goes
  through it. Text baselines come from glyph *tops* via `bl(top, size) =
  ry(top + BASE_K*size)`, where **`BASE_K = 0.665`** (derived from plate 25 and
  holds across 9/12/16 pt).
- **Job config shape.** `{"order": [{"plate": N, "data": {...}, "photo": path,
  "focal": [x,y], "boxes": [...]}]}`. The assembler classifies each plate from
  the manifest; `build` plates with a registered builder start from a blank page
  and call `BUILDERS[N](c, data, photo, focal)`. See `examples/`.
- **Builders registered** in `BUILDERS`: 25 (Property Summary), 35 (Sale Comps
  Summary), 41 (Rent Comps Summary), 37 & 38 (Sale Comps Detail), 44 & 45 (Rent
  Comps Charts). **Not yet built:** 1 (cover) and 4 (TOC) — they fall back to the
  corporate placeholder and log `build:NO-BUILDER`.
- **Shared helpers** (use these; don't re-invent):
  - `cell_text(c, x0, x1, top, text, font, size, colour, align, pad, track)` —
    the workhorse; supports left/center/right and letter-spacing.
  - `running_head(c, prefix, suffix)` — two-tone tracked page head + rule.
  - `hrule`, `fill_box`, `draw_star`, `draw_pin`, `stamp_icon`, `place`,
    `cover_crop` (focal-point scale-to-fill for photos).
  - `_build_comps_summary` (35/41), `_detail_block`/`_build_comps_detail`
    (37/38), `_chart_block` (44/45).

## Measured facts (do not re-derive)

- Page: **792 x 612 pt** landscape, 53 pages, uniform.
- Fonts: **Frank Ruhl Libre** (display; Regular/Medium/Bold/Black) and **Roboto**
  (UI). A MinionPro reference exists only in a dead legacy footer layer — ignore.
- Colors (screen hex): navy `#002B5C`, orange `#F58026`, ink `#222222`, grey band
  `#E5E7E6` (rendered ~`#E7E9EB`), gold star `#FFC736`.
- **Letter-spacing (tracking):** the bold column-header rows and the detail-block
  name/address are letter-spaced **~0.95 pt/char** (InDesign 95/1000 em). The
  16 pt page head uses ~1.6. Body/data rows are **not** tracked.
- Table right-edge alignment: numeric summary columns center, `CLOSE`/`RENT/SF`
  data right-align; header rows of the chart table center all columns.

## The measure / build / correct loop (how builders are made)

This is the load-bearing method. To build or fix a plate:

1. `python tools/inspect_plate.py <N>` — pack frames + corporate glyph
   positions (font, size, x0, top) for the plate.
2. `python tools/dump_graphics.py <N>` — rules, shaded rects, icon curves that
   text extraction misses.
3. Write/adjust the builder using those coordinates and the shared helpers.
4. `python tools/diff_plate.py examples/config_pXX_only.json <N> --show` —
   assembles the single plate, writes `build/cmp_pNN.png` (corporate on top,
   built below) and prints per-word `dx/dy` deltas.
5. Fold measured offsets back in as constants; repeat until deltas are noise.

A good result: `matched=<all> miss=0 max|dx|<~2 max|dy|<~0.6`, with residual dx
only on the tracked head and multi-word font-subset spacing.

## Gotchas learned the hard way

- **File encoding.** Always open JSON with `encoding='utf-8'`. On Windows the
  default is CP1252, which mangles dashes/curly-quotes/accents in real copy.
- **Char-spacing (Tc) leaks.** `Tc` is a PDF graphics-state parameter that
  survives `ET`; a tracked text run will bleed letter-spacing into every later
  `drawString`. `tracked()` and `cell_text(track=...)` wrap themselves in
  save/restore — keep it that way.
- **qpdf on PATH.** The assembler shells out to `qpdf` for final compression and
  falls back (uncompressed) if it's missing. On Windows add
  `C:\Program Files\qpdf <ver>\bin` to PATH; ignore the `2>/dev/null` cmd noise.
- **Column boundaries can bleed past the visible rule.** e.g. plate 35's CLOSE
  cell extends to x=756 though the row rule stops at 719.9. Trust measured text
  right-edges over the rule extents.
- **Icons.** Brand pictograms (plate 44 house/person/clock) are extracted from
  the corporate PDF as transparent PNGs in `assemble/assets/`; the star and
  numbered map-pins are drawn as vectors (`draw_star`, `draw_pin`).

## Known limitations (see ROADMAP.md)

Cover + TOC builders missing; console Assemble not wired; superseded footer text
not stripped from restamped pages; stamps leave the buried original image in the
file (size). None block the prototype.

## Dev environment on this machine

- Python: `C:\Users\<user>\AppData\Local\Programs\Python\Python312\python.exe`
- Packages: `reportlab pypdf pillow pyyaml pdfplumber pymupdf`
- qpdf: `C:\Program Files\qpdf 12.3.2\bin\qpdf.exe`
- `tools/` scripts derive repo root from their own path; run them with the
  Python above. `tools/diff_plate.py` writes to `build/` (git-ignored).
