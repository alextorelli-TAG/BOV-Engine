"""Dump the template pack's geometry + the corporate page's actual glyph
positions for one plate. This is the raw material for writing a builder.

    python tools/inspect_plate.py <plate_no> [--words]

All coordinates are points, origin TOP-LEFT (matching the pack and assembler).
Requires the split page library at page_library/ (see README) and pdfplumber.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = json.load(open(os.path.join(ROOT, "assemble", "bov_template_pack.json"),
                     encoding="utf-8"))
LIB = os.path.join(ROOT, "page_library")


def dump_frames(plate):
    pg = next((p for p in PACK["pages"] if p["page"] == plate), None)
    if not pg:
        print(f"no pack entry for plate {plate}"); return
    print(f"=== PACK plate {plate}  class={pg.get('class')}  "
          f"section={pg.get('footer_section')} ===")
    print(f"  text_frames={pg.get('text_frames')} "
          f"image_frames={pg.get('image_frames')} slots={pg.get('slots')}")
    print("  -- TEXT FRAMES [x0, top, x1, bottom] --")
    for i, fr in enumerate(pg.get("frames", [])):
        b = fr["box"]
        snip = fr.get("snippet", "").replace("\n", " \\n ")[:70]
        print(f"   [{i}] box=[{b[0]:.1f}, {b[1]:.1f}, {b[2]:.1f}, {b[3]:.1f}] "
              f"sizes={fr.get('sizes')}  {snip!r}")
    print("  -- IMAGE FRAMES [x0, top, x1, bottom] --")
    for slot, items in PACK["image_slots"].items():
        for it in items:
            if it["page"] == plate:
                b = it["box"]
                print(f"   {slot:16} box=[{b[0]:.1f}, {b[1]:.1f}, {b[2]:.1f}, "
                      f"{b[3]:.1f}] aspect={it['aspect']} link={it['link']}")


def dump_text(plate, words=False):
    import pdfplumber
    src = os.path.join(LIB, f"p{plate:02d}.pdf")
    if not os.path.exists(src):
        print(f"\n(no page library file {src}; run tools/split_library.py)"); return
    print(f"\n=== CORPORATE text p{plate:02d} (top-left coords) ===")
    with pdfplumber.open(src) as pdf:
        pg = pdf.pages[0]
        if words:
            for w in pg.extract_words(extra_attrs=["fontname", "size"]):
                print(f"  x0={w['x0']:7.2f} top={w['top']:7.2f} "
                      f"sz={w.get('size', 0):5.2f} {w.get('fontname', '?'):<26} "
                      f"{w['text']!r}")
            return
        runs, cur = [], None
        for ch in sorted(pg.chars, key=lambda c: (round(c['top'], 0), c['x0'])):
            key = (round(ch['top'], 1), ch['fontname'], round(ch['size'], 1))
            if cur and cur['key'] == key and ch['x0'] - cur['x1'] < 4:
                cur['text'] += ch['text']; cur['x1'] = ch['x1']
            else:
                if cur:
                    runs.append(cur)
                cur = {'key': key, 'text': ch['text'], 'x0': ch['x0'], 'x1': ch['x1'],
                       'top': ch['top'], 'bottom': ch['bottom'],
                       'font': ch['fontname'], 'size': ch['size']}
        if cur:
            runs.append(cur)
        for r in runs:
            t = r['text'].strip()
            if not t:
                continue
            print(f"  x0={r['x0']:7.2f} top={r['top']:6.2f} bot={r['bottom']:6.2f} "
                  f"sz={r['size']:5.2f} {r['font']:<26} {t!r}")


if __name__ == "__main__":
    plate = int(sys.argv[1])
    dump_frames(plate)
    dump_text(plate, words="--words" in sys.argv[2:])
