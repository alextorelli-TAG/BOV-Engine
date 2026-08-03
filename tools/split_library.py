"""Split the 53-page corporate master PDF into the single-page library the
assembler reads (page_library/p01.pdf .. p53.pdf).

    python tools/split_library.py "<path to corporate master .pdf>"

The master is proprietary and git-ignored; keep it locally. Verifies every
page is the expected 792 x 612 pt landscape.
"""
import os, sys
from pypdf import PdfReader, PdfWriter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "page_library")

src = sys.argv[1] if len(sys.argv) > 1 else None
if not src or not os.path.exists(src):
    sys.exit("usage: split_library.py <corporate_master.pdf>")

os.makedirs(OUT, exist_ok=True)
r = PdfReader(src)
sizes = set()
for i, p in enumerate(r.pages, 1):
    sizes.add((round(float(p.mediabox.width), 1), round(float(p.mediabox.height), 1)))
    w = PdfWriter()
    w.add_page(p)
    with open(os.path.join(OUT, f"p{i:02d}.pdf"), "wb") as f:
        w.write(f)
print(f"wrote {len(r.pages)} pages -> {OUT}")
print("distinct page sizes:", sizes)
if sizes != {(792.0, 612.0)}:
    print("WARNING: expected a single 792x612 size; template may have changed.")
