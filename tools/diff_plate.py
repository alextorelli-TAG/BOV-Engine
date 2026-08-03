"""Build one plate through the assembler and diff it against the corporate
original — the core of the measure/build/correct loop.

    python tools/diff_plate.py <config.json> <plate_no> [--show]

Produces (next to this repo's build/ dir):
  build/built_p<NN>.pdf   the assembled single plate
  build/cmp_p<NN>.png     corporate (top) vs built (bottom), stacked

and prints per-word x/y deltas. A word appears in the list only if |dx|>1 or
|dy|>1; --show also prints them. Footer band (top>560) is ignored because the
single-plate page number won't match the corporate original's.

Deps: reportlab, pypdf, pillow, pdfplumber, pymupdf. Put qpdf on PATH for the
assembler's final compression step (optional; it falls back without it).
"""
import io, json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "assemble"))
import assembler  # noqa: E402

LIB = os.path.join(ROOT, "page_library")
FONTS = os.path.join(ROOT, "fonts")
BUILD = os.path.join(ROOT, "build")
os.makedirs(BUILD, exist_ok=True)


def render(path, dpi=150):
    import fitz
    from PIL import Image
    pm = fitz.open(path)[0].get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    return Image.open(io.BytesIO(pm.tobytes("png")))


def words(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [w for w in pdf.pages[0].extract_words(extra_attrs=["fontname", "size"])
                if w["top"] < 560]


def landmark_diff(plate, built, show):
    corp = words(os.path.join(LIB, f"p{plate:02d}.pdf"))
    idx = defaultdict(list)
    for w in words(built):
        idx[w["text"]].append(w)
    dx_max = dy_max = 0.0
    matched = miss = 0
    for w in corp:
        cand = idx.get(w["text"], [])
        best, bd = None, 1e9
        for c in cand:
            if abs(c["top"] - w["top"]) < bd:
                bd, best = abs(c["top"] - w["top"]), c
        if best is None or bd > 8:
            miss += 1
            print(f"  {w['text'][:24]:24} corp x0={w['x0']:7.2f} top={w['top']:7.2f}  *** MISS ***")
            continue
        cand.remove(best)
        dx, dy = best["x0"] - w["x0"], best["top"] - w["top"]
        dx_max, dy_max = max(dx_max, abs(dx)), max(dy_max, abs(dy))
        matched += 1
        if show and (abs(dx) > 1 or abs(dy) > 1):
            print(f"  {w['text'][:24]:24} corp x0={w['x0']:7.2f} top={w['top']:7.2f} "
                  f" dx={dx:+6.2f} dy={dy:+6.2f}")
    extra = sum(len(v) for v in idx.values())
    print(f"\nmatched={matched} miss={miss}  max|dx|={dx_max:.2f}  max|dy|={dy_max:.2f}  "
          f"extra_built_words={extra}")


if __name__ == "__main__":
    cfg_path, plate = sys.argv[1], int(sys.argv[2])
    show = "--show" in sys.argv
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    built = os.path.join(BUILD, f"built_p{plate:02d}.pdf")
    _, log = assembler.assemble(cfg, LIB, built, FONTS)
    print("\n".join(log))
    from PIL import Image
    a, b = render(os.path.join(LIB, f"p{plate:02d}.pdf")), render(built)
    comp = Image.new("RGB", (max(a.width, b.width), a.height + b.height + 16), "white")
    comp.paste(a, (0, 0)); comp.paste(b, (0, a.height + 16))
    cmp_path = os.path.join(BUILD, f"cmp_p{plate:02d}.png")
    comp.save(cmp_path)
    print(f"built  -> {built}")
    print(f"compare-> {cmp_path}")
    landmark_diff(plate, built, show)
