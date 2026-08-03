"""Dump the vector graphics (rules, filled rects, icon curves) of a corporate
plate. Text extraction alone misses table rules, shaded bands, and icons —
this fills that gap when reverse-engineering a builder.

    python tools/dump_graphics.py <plate_no>

Coordinates are points, origin TOP-LEFT. Stroke/fill colours are as reported
by pdfplumber (CMYK tuples for the InDesign swatches, RGB for a few).
"""
import os, sys, pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "page_library")

plate = int(sys.argv[1])
with pdfplumber.open(os.path.join(LIB, f"p{plate:02d}.pdf")) as pdf:
    pg = pdf.pages[0]
    print(f"page size: {pg.width} x {pg.height}")
    print(f"\n-- LINES ({len(pg.lines)}) --")
    for l in sorted(pg.lines, key=lambda l: (round(l['top'], 0), l['x0'])):
        print(f"  ({l['x0']:.1f},{l['top']:.1f}) -> ({l['x1']:.1f},{l['bottom']:.1f}) "
              f"w={l.get('linewidth', 0):.2f} stroke={l.get('stroking_color')}")
    print(f"\n-- RECTS ({len(pg.rects)}) --")
    for r in sorted(pg.rects, key=lambda r: (round(r['top'], 0), r['x0'])):
        print(f"  x0={r['x0']:.1f} top={r['top']:.1f} x1={r['x1']:.1f} bot={r['bottom']:.1f} "
              f"fill={r.get('non_stroking_color')} stroke={r.get('stroking_color')} "
              f"lw={r.get('linewidth', 0):.2f}")
    print(f"\n-- CURVES ({len(pg.curves)}) --")
    for cu in sorted(pg.curves, key=lambda c: (round(c['top'], 0), c['x0'])):
        print(f"  x0={cu['x0']:.1f} top={cu['top']:.1f} x1={cu['x1']:.1f} "
              f"bot={cu['bottom']:.1f} fill={cu.get('non_stroking_color')}")
