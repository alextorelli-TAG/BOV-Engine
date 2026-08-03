# Brand assets

Raw Marcus & Millichap / The Anton Group logos used by the page builders.
**Use the raw source assets here — do not recreate logos from screenshots or by
extracting them from the corporate PDF.**

Expected files (referenced by the builders via `stamp_icon('brand/<name>')`):

| File | Used by | Notes |
|---|---|---|
| `mm_logo_white.png` | Cover (1), dividers, back cover | white logo for navy grounds; transparent bg |
| `mm_logo_navy.png` | Table of Contents (4) | navy logo for white grounds; transparent bg |
| `mm_tag_lockup_white.png` | dividers, back cover | M&M + The Anton Group lockup (as needed) |

Prefer vector source (SVG/PDF/EPS) committed alongside; rasterize to a high-res
transparent PNG once (≥1000 px on the long edge) at the names above. A builder
skips a missing asset gracefully, so pages render without the logo until the
raw files are added here.
