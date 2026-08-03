# Brand assets

Raw Marcus & Millichap / The Anton Group logos used by the page builders.
**Use the raw source assets here — do not recreate logos from screenshots or by
extracting them from the corporate PDF.**

**The Anton Group lockup is the default** (Marcus & Millichap over THE ANTON
GROUP). Referenced by builders via `stamp_icon('brand/<name>', ..., fit=True)`.

| File | Used by | Notes |
|---|---|---|
| `anton_group_lockup_white.png` | Cover (1), dividers, back cover | white lockup for navy grounds; rasterized from the white SVG (crisp) |
| `anton_group_lockup_navy.png` | Table of Contents (4) | navy lockup for white grounds; recolored from the white SVG so it matches the white version exactly |
| `anton_group_lockup_white.svg` | (source) | vector master for both PNGs above |
| `anton_group_lockup_parchment.png` | — | warmer cream variant (lower-res raster); available if a softer tone is wanted |
| `mm_logo_white.png` / `mm_logo_navy.png` | — | Marcus & Millichap-only wordmarks (no Anton Group); alternates |

To regenerate the PNGs from the SVG (white + navy), rasterize the SVG at
~2400 px wide with PyMuPDF and, for navy, remap the white pixels to `#002B5C`
while preserving alpha. Builders skip a missing asset gracefully.
