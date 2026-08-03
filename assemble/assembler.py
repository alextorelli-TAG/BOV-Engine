#!/usr/bin/env python3
"""BOV assembler.

Takes a config of the shape the console emits and produces a PDF.

Four operations, matching the four page classes in the manifest:

  passthrough  copy a page from the corporate library, byte-identical
  stamp        copy a corporate page, then composite an image into a frame
  build        render the page from scratch at the pack's coordinates
  restamp      white-box the footer band and redraw the corrected page number

Coordinates throughout are the pack's: points, origin top-left, y increasing
downward. reportlab wants bottom-left, so every draw call goes through `ry()`.
"""
import io, json, os, sys
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

ROOT = os.path.dirname(os.path.abspath(__file__))
PACK = json.load(open(os.path.join(ROOT, 'bov_template_pack.json'), encoding='utf-8'))
PAGE_W, PAGE_H = PACK['page']['width'], PACK['page']['height']

C = {k: v['hex'] for k, v in PACK['tokens']['color_resolved'].items()}
# The footer band's swatch is #B0B7BC but it renders with transparency applied.
# Measured off the corporate PDF at 288dpi:
C['grey_band'] = '#E7E9EB'

FONTS = {
    'FRL':       'FrankRuhlLibre-Regular.ttf',
    'FRL-Med':   'FrankRuhlLibre-Medium.ttf',
    'FRL-Bold':  'FrankRuhlLibre-Bold.ttf',
    'FRL-Black': 'FrankRuhlLibre-Black.ttf',
}


def register_fonts(font_dir):
    missing = []
    for name, fn in FONTS.items():
        p = os.path.join(font_dir, fn)
        if os.path.exists(p):
            pdfmetrics.registerFont(TTFont(name, p))
        else:
            missing.append(fn)
    if missing:
        raise RuntimeError(f'missing fonts: {missing}. The Albemarle draft fell '
                           f'back to DejaVu for exactly this reason.')


def ry(y):
    """Top-left y -> reportlab bottom-left y."""
    return PAGE_H - y


def hexcol(c):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def tracked(c, x, y, text, font, size, tracking=0.0, colour=None):
    """Draw letterspaced text. The corporate heads and footer labels are
    tracked, and canvas.drawString can't express that -- only text objects can.
    Returns the advance width so runs can be chained.

    Wrapped in save/restore: the PDF char-spacing operator (Tc) is a
    graphics-state parameter that survives ET, so without this the tracking
    would leak into every subsequent drawString on the page."""
    c.saveState()
    t = c.beginText(x, y)
    t.setFont(font, size)
    if colour:
        t.setFillColorRGB(*colour)
    t.setCharSpace(tracking)
    t.textOut(text)
    c.drawText(t)
    c.restoreState()
    return pdfmetrics.stringWidth(text, font, size) + tracking * len(text)


# ------------------------------------------------------------------ images
def cover_crop(path, w_pt, h_pt, focal=(0.5, 0.5), dpi=200, quality=82):
    """Scale-to-fill a frame, cropping around a focal point. This is the
    operation that keeps rooflines in frame across 11 aspect ratios.

    Returns a JPEG-encoded ImageReader. Handing reportlab a raw PIL image makes
    it Flate-encode the pixels, which took a 19-page book to 127 MB.
    """
    im = Image.open(path).convert('RGB')
    W, H = im.size
    target = w_pt / h_pt
    src = W / H
    if src > target:                       # source too wide, trim sides
        nw = int(H * target)
        left = int((W - nw) * focal[0])
        left = max(0, min(W - nw, left))
        im = im.crop((left, 0, left + nw, H))
    else:                                  # source too tall, trim top/bottom
        nh = int(W / target)
        top = int((H - nh) * focal[1])
        top = max(0, min(H - nh, top))
        im = im.crop((0, top, W, top + nh))
    px = (max(1, int(w_pt / 72 * dpi)), max(1, int(h_pt / 72 * dpi)))
    if im.size[0] > px[0]:
        im = im.resize(px, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=quality, optimize=True, progressive=True)
    buf.seek(0)
    return ImageReader(buf)


def place(c, path, box, focal, dpi=200):
    c.drawImage(cover_crop(path, box[2] - box[0], box[3] - box[1], focal, dpi),
                box[0], ry(box[3]), box[2] - box[0], box[3] - box[1])


ASSETS = os.path.join(ROOT, 'assets')


def stamp_icon(c, name, box, fit=False):
    """Draw a transparent PNG at `box`. With fit=True, scale to fit inside the
    box preserving aspect ratio, centred (used for logos so they don't stretch);
    otherwise stretch to fill (used for pictograms/scrims sized to their clip)."""
    p = os.path.join(ASSETS, name)
    if not os.path.exists(p):
        return
    x0, top, x1, bot = box
    w, h = x1 - x0, bot - top
    if fit:
        iw, ih = ImageReader(p).getSize()
        asp = iw / ih
        if w / h > asp:                     # box wider than image -> fit height
            nw = h * asp
            x0 += (w - nw) / 2
            w = nw
        else:                               # box taller -> fit width
            nh = w / asp
            top += (h - nh) / 2
            h = nh
    c.drawImage(p, x0, ry(top + h), w, h, mask='auto')


# ------------------------------------------------------------ draw helpers
# InDesign glyph "top" (bbox top) -> reportlab baseline. Derived from the
# plate-25 landmarks: baseline = top + 0.665*size held across 9/12/16 pt.
BASE_K = 0.665


def bl(top, size):
    """Top-left glyph top -> reportlab baseline y."""
    return ry(top + BASE_K * size)


def cell_text(c, x0, x1, top, text, font, size, colour, align='left', pad=4.0,
              track=0.0):
    """Draw one table cell's text, aligned within [x0, x1]. `top` is the
    corporate glyph top; baseline is derived via BASE_K. `track` is per-char
    letter-spacing in points (the corporate header row uses ~0.95)."""
    if text is None or text == '':
        return
    text = str(text)
    n = len(text)
    w = pdfmetrics.stringWidth(text, font, size) + (track * (n - 1) if n > 1 else 0)
    if align == 'left':
        xx = x0 + pad
    elif align == 'right':
        xx = x1 - pad - w
    else:                                   # center
        xx = (x0 + x1) / 2 - w / 2
    if track:
        c.saveState()
        t = c.beginText(xx, bl(top, size))
        t.setFont(font, size)
        t.setFillColorRGB(*colour)
        t.setCharSpace(track)
        t.textOut(text)
        c.drawText(t)
        c.restoreState()
    else:
        c.setFont(font, size)
        c.setFillColorRGB(*colour)
        c.drawString(xx, bl(top, size), text)


def hrule(c, x0, y, x1, width, colour):
    c.setStrokeColorRGB(*colour)
    c.setLineWidth(width)
    c.line(x0, ry(y), x1, ry(y))


def fill_box(c, box, colour):
    c.setFillColorRGB(*colour)
    c.rect(box[0], ry(box[3]), box[2] - box[0], box[3] - box[1], stroke=0, fill=1)


def running_head(c, prefix, suffix):
    """Two-tone letterspaced page head + underline rule, shared by all built
    plates. Measured: glyph top 68.7 -> baseline 79.4 at 16pt; rule at y=89.7,
    x 0->756, ink, 1.0pt. Matches the corporate template exactly."""
    navy, orange = hexcol(C['navy']), hexcol(C['orange'])
    w = tracked(c, 36.0, ry(79.4), prefix, 'FRL', 16, 1.6, navy)
    tracked(c, 36.0 + w, ry(79.4), suffix, 'FRL-Bold', 16, 1.6, orange)
    hrule(c, 0.0, 89.7, 756.0, 1.0, hexcol(C['ink']))


def draw_star(c, cx, cy, r, colour, points=5, inner_ratio=0.44):
    """Filled n-point star centred at (cx, cy) in top-left coords, outer
    radius r. Used for the subject-property marker in comps summaries."""
    import math
    c.setFillColorRGB(*colour)
    p = c.beginPath()
    for i in range(points * 2):
        rad = r if i % 2 == 0 else r * inner_ratio
        ang = -math.pi / 2 + i * math.pi / points
        x = cx + rad * math.cos(ang)
        y = cy + rad * math.sin(ang)      # top-left y grows downward
        if i == 0:
            p.moveTo(x, ry(y))
        else:
            p.lineTo(x, ry(y))
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def draw_pin(c, box, number, fill, text_colour):
    """Navy numbered map-pin (teardrop) inside the icon-column box
    [x0, top, x1, bottom], top-left coords. Circle up top, point at bottom."""
    x0, top, x1, bot = box
    cx = (x0 + x1) / 2
    r = (x1 - x0) / 2
    cyc = top + r                          # circle centre
    tip = bot                              # point
    c.setFillColorRGB(*fill)
    # circle
    c.circle(cx, ry(cyc), r, stroke=0, fill=1)
    # triangle from circle's lower flanks down to the tip
    p = c.beginPath()
    p.moveTo(cx - r * 0.70, ry(cyc + r * 0.55))
    p.lineTo(cx + r * 0.70, ry(cyc + r * 0.55))
    p.lineTo(cx, ry(tip))
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    # number, centred in the circle
    s = 8
    c.setFont('FRL-Bold', s)
    c.setFillColorRGB(*text_colour)
    tw = pdfmetrics.stringWidth(str(number), 'FRL-Bold', s)
    c.drawString(cx - tw / 2, ry(cyc) - s * 0.34, str(number))


# ---------------------------------------------------------------- overlays
def new_overlay():
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    return buf, c


def finish_overlay(buf, c):
    c.showPage()          # an overlay with no marks still has to emit a page
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def draw_footer(c, n, section):
    """White-box the grey band and redraw the page number. Geometry from the
    pack: band [0, 578.79, 233.28, 595.13], number box [23.54, 581.98,
    58.54, 590.6], pipe at x=53.1, label from x=60.5."""
    band = PACK['tokens']['footer']['band']
    c.setFillColorRGB(*hexcol(C['grey_band']))
    c.rect(band[0], ry(band[3]), band[2] - band[0], band[3] - band[1],
           stroke=0, fill=1)
    navy = hexcol(C['navy'])
    c.setFillColorRGB(*navy)
    c.setFont('FRL-Bold', 9)
    c.drawRightString(49.0, ry(590.2), str(n))
    if section:
        c.setStrokeColorRGB(*navy)
        c.setLineWidth(0.5)
        c.line(53.1, ry(590.6), 53.1, ry(584.5))
        tracked(c, 60.5, ry(590.2), section, 'FRL-Med', 9, 1.15, navy)


# ------------------------------------------------------------ plate builds
def build_plate25(c, d, photo=None, focal=(0.5, 0.5)):
    """Property Summary, rendered from the pack's own frame boxes."""
    navy, orange, ink = hexcol(C['navy']), hexcol(C['orange']), hexcol(C['ink'])

    # running head, two-tone, letterspaced -- frame [36.0, 64.8, 653.0, 89.7]
    HEAD_BASE = 79.4          # measured: corporate glyph top at 68.7
    w = tracked(c, 36.0, ry(HEAD_BASE), 'PROPERTY SUMMARY // ', 'FRL', 16, 1.6, navy)
    tracked(c, 36.0 + w, ry(HEAD_BASE), 'SUBJECT PROPERTY', 'FRL-Bold', 16, 1.6, orange)

    # rule under the head -- GraphicLine [36.0, 89.7, 792.0, 89.7]
    c.setStrokeColorRGB(*navy)
    c.setLineWidth(1.1)
    c.line(36.0, ry(89.7), 792.0, ry(89.7))

    # hero photo -- Rectangle [407.2, 124.6, 792.0, 306.0], bleeds right
    if photo and os.path.exists(photo):
        place(c, photo, [407.2, 124.6, 792.0, 306.0], focal)

    # ---- description + highlights, frame [36.0, 124.6, 384.8, 495.5]
    x0, y, x1 = 36.0, 124.6, 384.75
    measure = x1 - x0
    c.setFont('FRL-Bold', 12)
    c.setFillColorRGB(*navy)
    c.drawString(x0, ry(y + 11.3), 'PROPERTY DESCRIPTION')   # +2.3 measured
    y += 22.3

    c.setFillColorRGB(*ink)
    for para in d.get('description', []):
        for line in wrap(c, para, 'FRL', 9, measure):
            c.setFont('FRL', 9)
            c.drawString(x0, ry(y + 5.1), line)   # -1.4 measured
            y += 14
        y += 2

    y += 8
    c.setFont('FRL-Bold', 12)
    c.setFillColorRGB(*navy)
    c.drawString(x0, ry(y + 9), 'PROPERTY HIGHLIGHTS')
    y += 20

    for b in d.get('highlights', []):
        c.setFillColorRGB(*orange)
        c.setFont('FRL-Bold', 10)
        c.drawString(x0, ry(y + 7), '\u2022')
        c.setFillColorRGB(*ink)
        for i, line in enumerate(wrap(c, b, 'FRL', 10, measure - 12)):
            c.setFont('FRL', 10)
            c.drawString(x0 + 12, ry(y + 7), line)
            y += 15 if i == 0 else 13
        y += 3

    # ---- offering summary, frame [407.2, 326.0, 756.0, 510.1]
    ox0, oy, ox1 = 407.2 + 4.0, 326.0, 756.0     # 4pt inset, measured
    c.setFont('FRL-Bold', 12)
    c.setFillColorRGB(*navy)
    c.drawString(ox0, ry(oy + 17.1), 'OFFERING SUMMARY')   # +8.1 measured
    oy += 23.0
    rows = d.get('offering', [])
    for label, val in rows:
        c.setStrokeColorRGB(0.82, 0.83, 0.84)
        c.setLineWidth(0.4)
        c.line(ox0, ry(oy), ox1, ry(oy))
        c.setFont('FRL', 9)
        c.setFillColorRGB(*ink)
        c.drawString(ox0 + 4, ry(oy + 14), label)
        c.drawRightString(ox1 - 4, ry(oy + 14), str(val))
        oy += 20.15                                # corporate row pitch
    c.setStrokeColorRGB(0.82, 0.83, 0.84)
    c.line(ox0, ry(oy), ox1, ry(oy))


# --- shared comps-table column model (plates 35/37/41/44 build on this) -----
# InDesign cell boundaries measured off the corporate table, top-left coords.
# (key, x0, x1, align) — align applies to both header and data.
SALE_COLS = [
    ('label', 113.0, 266.4, 'left'),
    ('price', 266.4, 361.4, 'left'),
    ('bldg',  361.4, 434.9, 'center'),
    ('ppu',   434.9, 524.2, 'center'),
    ('cap',   524.2, 571.0, 'center'),
    ('units', 571.0, 641.5, 'center'),
    ('close', 641.5, 719.9, 'right'),    # header + data share right edge 715.9
]
SALE_HEADERS = {'price': 'PRICE', 'bldg': 'BLDG SF', 'ppu': 'PRICE/UNIT',
                'cap': 'CAP', 'units': '# OF UNITS', 'close': 'CLOSE'}

TABLE_X0, TABLE_X1 = 36.0, 719.9        # full table extent incl. icon column
ROW_L1, ROW_L2, ROW_L3 = 0.0, 13.7, 27.4  # name / data+address / city offsets


def _comps_row(c, cols, name_top, row, navy, ink):
    """One 3-line comp/subject row. `name_top` is the glyph top of line 1."""
    cell_text(c, 113.0, 266.4, name_top, row.get('name'), 'FRL-Bold', 9, navy)
    y2 = name_top + ROW_L2
    cell_text(c, 113.0, 266.4, y2, row.get('address'), 'FRL', 9, ink)
    for key, x0, x1, align in cols[1:]:
        cell_text(c, x0, x1, y2, row.get(key), 'FRL', 9, ink, align)
    cell_text(c, 113.0, 266.4, name_top + ROW_L3, row.get('city'), 'FRL', 9, ink)


HEADER_TRACK = 0.95     # corporate letter-spaces the bold 10pt header row


def _comps_header(c, cols, top, label, navy):
    """Column header row: section label in the name column + column titles."""
    cell_text(c, 113.0, 266.4, top, label, 'FRL-Bold', 10, navy, track=HEADER_TRACK)
    for key, x0, x1, align in cols[1:]:
        cell_text(c, x0, x1, top, SALE_HEADERS.get(key, ''), 'FRL-Bold', 10, navy,
                  align, track=HEADER_TRACK)


def _build_comps_summary(c, d, prefix, section_label):
    """Shared comps-summary body: subject row + up to 6 comps + totals band.
    Plates 35 (sale) and 41 (rent) are identical apart from `prefix` and
    `section_label`. Geometry measured off the corporate tables."""
    navy, ink = hexcol(C['navy']), hexcol(C['ink'])
    gold = hexcol('#FFC736')

    running_head(c, prefix, d.get('property', 'SUBJECT PROPERTY'))

    # ---- subject table ---------------------------------------------------
    _comps_header(c, SALE_COLS, 106.19, 'SUBJECT PROPERTY', navy)
    hrule(c, TABLE_X0, 118.7, TABLE_X1, 0.5, ink)
    draw_star(c, 74.25, 142.25, 10.5, gold)
    _comps_row(c, SALE_COLS, 125.75, d.get('subject', {}), navy, ink)
    hrule(c, TABLE_X0, 165.6, TABLE_X1, 0.25, ink)

    # ---- comparables table ----------------------------------------------
    _comps_header(c, SALE_COLS, 192.76, section_label, navy)
    hrule(c, TABLE_X0, 205.3, TABLE_X1, 0.5, ink)
    comps = d.get('comps', [])[:6]
    name_top0, pitch = 212.31, 46.87
    row_rules = [252.2, 299.0, 345.9, 392.8, 439.7, 486.5]
    for i in range(6):
        pin_box = [66.6, 220.8 + i * pitch, 82.4, 242.5 + i * pitch]
        draw_pin(c, pin_box, i + 1, navy, (1, 1, 1))
        if i < len(comps):
            _comps_row(c, SALE_COLS, name_top0 + i * pitch, comps[i], navy, ink)
        hrule(c, TABLE_X0, row_rules[i], TABLE_X1, 0.25, ink)

    # ---- totals / averages band -----------------------------------------
    fill_box(c, [TABLE_X0, 486.5, TABLE_X1, 505.4], hexcol(C['grey_band']))
    tot = d.get('totals', {})
    cell_text(c, 113.0, 266.4, 493.55, 'TOTALS/AVERAGEs', 'FRL-Bold', 9, navy)
    for key, x0, x1, align in SALE_COLS[1:]:
        if key == 'close':
            continue
        cell_text(c, x0, x1, 493.55, tot.get(key), 'FRL', 9, ink, align)
    hrule(c, TABLE_X0, 505.4, TABLE_X1, 0.25, (0, 0, 0))


def build_plate35(c, d, photo=None, focal=(0.5, 0.5)):
    """Sale Comps Summary."""
    _build_comps_summary(c, d, 'SALE COMPS SUMMARY // ', 'SALES COMPARABLES')


def build_plate41(c, d, photo=None, focal=(0.5, 0.5)):
    """Rent Comps Summary — identical layout to plate 35."""
    _build_comps_summary(c, d, 'RENT COMPS SUMMARY // ', 'RENT COMPARABLES')


# --- comps DETAIL blocks (plates 37/38 sale, 44/45 rent) --------------------
# Two mirrored blocks per page. Left base x=36, right base x=403.9. All
# geometry below is expressed relative to a block's base x (`bx`).
DETAIL_PHOTO = (0.0, 124.6, 316.1, 294.6)          # relative box
DETAIL_ROWS_A = [                                   # (label, value_key) col A
    ('Sale Date', 'sale_date'), ('Cap Rate', 'cap_rate'),
    ('NOI', 'noi'), ('Gross Square Feet', 'gross_sf')]
DETAIL_ROWS_B = [                                   # (label, value_key) col B
    ('Lot Size', 'lot_size'), ('Year Built', 'year_built'),
    ('Number of Units', 'num_units'), ('Occupancy %', 'occupancy')]
DETAIL_ROW_TOPS = [358.69, 376.30, 393.91, 411.53]
DETAIL_ROW_RULES = [352.0, 369.6, 387.2, 404.8]
UNIT_COLS = [                                       # (key, x0, x1, align) rel bx
    ('type',    0.0,   123.8, 'left'),
    ('units',   123.8, 170.6, 'center'),
    ('size',    170.6, 218.9, 'center'),
    ('rent',    218.9, 264.2, 'center'),
    ('rent_sf', 264.2, 316.1, 'right'),
]
UNIT_HEADERS = {'type': 'UNIT TYPE', 'units': '# UNITS', 'size': 'SIZE SF',
                'rent': 'RENT', 'rent_sf': 'RENT/SF'}
UNIT_ROW_TOPS = [455.41, 473.03, 490.64]
UNIT_ROW_RULES = [466.3, 483.9]


def _detail_block(c, bx, block):
    """Render one comp detail block at base x `bx`."""
    navy, ink = hexcol(C['navy']), hexcol(C['ink'])
    grey, gold = hexcol(C['grey_band']), hexcol('#FFC736')
    W = 316.1

    # photo (navy placeholder behind, in case no image is bound)
    pbox = [bx + DETAIL_PHOTO[0], DETAIL_PHOTO[1], bx + DETAIL_PHOTO[2], DETAIL_PHOTO[3]]
    fill_box(c, pbox, navy)
    if block.get('photo') and os.path.exists(block['photo']):
        place(c, block['photo'], pbox, tuple(block.get('focal', (.5, .5))))

    # icon
    icon = block.get('icon')
    if icon == 'star':
        draw_star(c, bx + 10.45, 316.3, 10.45, gold)
    elif icon is not None:
        draw_pin(c, [bx + 2.6, 308.6, bx + 18.3, 330.2], icon, navy, (1, 1, 1))

    # name + address (navy, letter-spaced)
    cell_text(c, bx + 26, 0, 308.15, block.get('name', ''), 'FRL-Bold', 10, navy,
              'left', pad=0, track=0.95)
    cell_text(c, bx + 26, 0, 319.82, block.get('address', ''), 'FRL', 10, navy,
              'left', pad=0, track=0.95)

    # price row (shaded)
    fill_box(c, [bx, 334.4, bx + W, 352.0], grey)
    cell_text(c, bx + 4, 0, 341.07, 'Price', 'FRL', 9, ink, 'left', pad=0)
    cell_text(c, 0, bx + 312.2, 341.07, block.get('price'), 'FRL', 9, ink, 'right', pad=0)

    # detail grid
    det = block.get('detail', {})
    for (labA, kA), (labB, kB), top in zip(DETAIL_ROWS_A, DETAIL_ROWS_B, DETAIL_ROW_TOPS):
        cell_text(c, bx + 4, 0, top, labA, 'FRL', 9, ink, 'left', pad=0)
        cell_text(c, 0, bx + 149.0, top, det.get(kA), 'FRL', 9, ink, 'right', pad=0)
        cell_text(c, bx + 169.6, 0, top, labB, 'FRL', 9, ink, 'left', pad=0)
        cell_text(c, 0, bx + 312.0, top, det.get(kB), 'FRL', 9, ink, 'right', pad=0)
    for y in DETAIL_ROW_RULES:
        hrule(c, bx, y, bx + W, 0.25, ink)

    # unit-type table
    for key, x0, x1, align in UNIT_COLS:
        cell_text(c, bx + x0, bx + x1, 436.84, UNIT_HEADERS[key], 'FRL-Bold', 9, navy,
                  align, track=0.95)
    hrule(c, bx, 448.7, bx + W, 0.5, ink)
    rows = block.get('unit_rows', [])[:3]
    for i, top in enumerate(UNIT_ROW_TOPS):
        if i < len(rows):
            r = rows[i]
            lines = wrap(c, str(r.get('type', '')), 'FRL', 9, 123.8 - 8)
            for j, ln in enumerate(lines[:2]):
                cell_text(c, bx + 4, 0, top + j * 10, ln, 'FRL', 9, ink, 'left', pad=0)
            for key, x0, x1, align in UNIT_COLS[1:]:
                cell_text(c, bx + x0, bx + x1, top, r.get(key), 'FRL', 9, ink, align)
        if i < len(UNIT_ROW_RULES):
            hrule(c, bx, UNIT_ROW_RULES[i], bx + W, 0.25, ink)

    # total/avg row (shaded)
    fill_box(c, [bx, 511.5, bx + W, 529.2], grey)
    tot = block.get('unit_total', {})
    cell_text(c, bx + 4, 0, 518.25, 'TOTAL/AVG', 'FRL', 9, ink, 'left', pad=0)
    for key, x0, x1, align in UNIT_COLS[1:]:
        cell_text(c, bx + x0, bx + x1, 518.25, tot.get(key), 'FRL', 9, ink, align)


def _build_comps_detail(c, d, prefix):
    """Two comp detail blocks side by side. d = {left:{...}, right:{...}}."""
    running_head(c, prefix, d.get('property', 'SUBJECT PROPERTY'))
    if d.get('left'):
        _detail_block(c, 36.0, d['left'])
    if d.get('right'):
        _detail_block(c, 403.9, d['right'])


def build_plate37(c, d, photo=None, focal=(0.5, 0.5)):
    """Sale Comps Detail — two comps per page."""
    _build_comps_detail(c, d, 'SALE COMPS // ')


# --- rent comps CHARTS (plates 44/45): two stacked blocks -------------------
CHART_ROW_DY = 227.76           # row 1 -> row 2 vertical offset
UNIT44_COLS = [                 # unit table, absolute x (fixed at 288..715.2)
    ('type',    288.0, 440.4, 'left'),
    ('units',   440.4, 490.8, 'center'),
    ('size',    490.8, 574.8, 'center'),
    ('rent',    574.8, 658.8, 'center'),
    ('rent_sf', 658.8, 715.2, 'right'),
]
UNIT44_HEADERS = {'type': 'UNIT TYPE', 'units': '# UNITS', 'size': 'SQUARE FEET',
                  'rent': 'RENT', 'rent_sf': 'RENT/SF'}
CHART_STATS = [                 # (asset, clip_box_row1, text_x, data_key)
    ('icon_units.png',     (411.5, 128.8, 428.5, 143.8), 431.43, 'units'),
    ('icon_occupancy.png', (486.5, 129.0, 500.0, 143.5), 503.50, 'occupancy'),
    ('icon_year.png',      (619.5, 129.8, 634.5, 144.5), 637.13, 'year'),
]
CHART_ROW_RULES = [196.9, 214.5, 232.2, 249.2, 266.2, 283.2, 300.2]


def _chart_block(c, dy, block):
    """One rent-comps chart block (photo + stat header + unit table) at
    vertical offset `dy`."""
    navy, ink = hexcol(C['navy']), hexcol(C['ink'])
    orange, grey, gold = hexcol(C['orange']), hexcol(C['grey_band']), hexcol('#FFC736')

    # icon + name + address
    icon = block.get('icon')
    if icon == 'star':
        draw_star(c, 46.45, 135.3 + dy, 10.45, gold)
    elif icon is not None:
        draw_pin(c, [37.7, 127.0 + dy, 55.1, 150.5 + dy], icon, navy, (1, 1, 1))
    cell_text(c, 62, 0, 127.18 + dy, block.get('name', ''), 'FRL-Bold', 10, navy,
              'left', pad=0, track=0.95)
    cell_text(c, 62, 0, 138.85 + dy, block.get('address', ''), 'FRL', 10, navy,
              'left', pad=0, track=0.95)

    # stat cluster: pictogram + value, with orange dividers
    stats = block.get('stats', {})
    for asset, clip, tx, key in CHART_STATS:
        stamp_icon(c, asset, [clip[0], clip[1] + dy, clip[2], clip[3] + dy])
        cell_text(c, tx, 0, 132.61 + dy, stats.get(key, ''), 'FRL', 11, navy, 'left', pad=0)
    c.setStrokeColorRGB(*orange)
    c.setLineWidth(0.74)
    for x in (481.0, 615.0):
        c.line(x, ry(128.0 + dy), x, ry(146.0 + dy))
    hrule(c, 36.0, 155.2 + dy, 715.2, 0.25, orange)

    # photo (navy placeholder behind)
    pbox = [36.0, 168.3 + dy, 262.8, 318.9 + dy]
    fill_box(c, pbox, navy)
    if block.get('photo') and os.path.exists(block['photo']):
        place(c, block['photo'], pbox, tuple(block.get('focal', (.5, .5))))

    # unit-type table (header type label has no left pad; data does)
    cell_text(c, 288.0, 0, 169.02 + dy, 'UNIT TYPE', 'FRL-Bold', 9, navy, 'left',
              pad=0, track=0.95)
    for key, x0, x1, align in UNIT44_COLS[1:]:
        # headers are all centred in this table (data keeps its column align)
        cell_text(c, x0, x1, 169.02 + dy, UNIT44_HEADERS[key], 'FRL-Bold', 9, navy,
                  'center', track=0.95)
    hrule(c, 288.0, 179.3 + dy, 715.2, 0.5, ink)
    rows = block.get('unit_rows', [])[:3]
    for i, top in enumerate([186.03, 203.64, 221.26]):
        if i < len(rows):
            r = rows[i]
            cell_text(c, 292.0, 0, top + dy, r.get('type', ''), 'FRL', 9, ink, 'left', pad=0)
            for key, x0, x1, align in UNIT44_COLS[1:]:
                cell_text(c, x0, x1, top + dy, r.get(key), 'FRL', 9, ink, align)
    for y in CHART_ROW_RULES:
        hrule(c, 288.0, y + dy, 715.2, 0.25, ink)

    # total/avg row (shaded)
    fill_box(c, [288.0, 300.2 + dy, 715.2, 317.8 + dy], grey)
    tot = block.get('unit_total', {})
    cell_text(c, 292.0, 0, 306.87 + dy, 'TOTAL/AVG', 'FRL', 9, ink, 'left', pad=0)
    for key, x0, x1, align in UNIT44_COLS[1:]:
        cell_text(c, x0, x1, 306.87 + dy, tot.get(key), 'FRL', 9, ink, align)


TOC_SECTIONS = ['Marcus & Millichap Advantage', 'Advisor Bios', 'Marketing Plan',
                'Investment Overview', 'Financial Analysis', 'Sale Comparables',
                'Rent Comparables', 'Market Overview']


def build_plate4(c, d, photo=None, focal=(0.5, 0.5)):
    """Table of Contents: left photo + section list. Generated last, so the
    sections list reflects which survived selection (renumbered 1..N)."""
    navy, orange = hexcol(C['navy']), hexcol(C['orange'])
    grey = (0.69, 0.718, 0.737)

    if photo and os.path.exists(photo):
        place(c, photo, [0.0, 0.0, 360.0, 612.0], focal)
    else:
        fill_box(c, [0.0, 0.0, 360.0, 612.0], navy)

    cell_text(c, 432.0, 0, 71.28, 'TABLE OF CONTENTS', 'FRL-Med', 18, navy,
              'left', pad=0, track=2.5)
    hrule(c, 432.0, 96.0, 720.0, 3.0, navy)

    sections = d.get('sections', TOC_SECTIONS)
    for i, sec in enumerate(sections[:8]):
        top = 117.77 + i * 51.14
        title = sec.get('title') if isinstance(sec, dict) else sec
        num = sec.get('num', i + 1) if isinstance(sec, dict) else i + 1
        cell_text(c, 432.0, 0, top, f'SECTION {num}', 'FRL', 9, orange, 'left',
                  pad=0, track=0.9)
        cell_text(c, 432.0, 0, top + 12.94, title, 'FRL-Bold', 11, navy, 'left', pad=0)
        if i < len(sections) - 1:
            hrule(c, 432.0, 148.4 + i * 51.14, 720.0, 0.25, navy)

    hrule(c, 0.0, 594.1, 360.0, 1.0, grey)
    hrule(c, 360.0, 594.1, 792.0, 1.0, navy)
    stamp_icon(c, 'brand/mm_logo_navy.png', [432.0, 544.3, 572.0, 563.5], fit=True)


def build_plate1(c, d, photo=None, focal=(0.5, 0.5)):
    """Cover: full-bleed property photo + navy scrim, PROPOSAL bar, title/
    address, and the Marcus & Millichap logo box."""
    navy, orange = hexcol(C['navy']), hexcol(C['orange'])

    if photo and os.path.exists(photo):
        place(c, photo, [0.0, 0.0, 792.0, 612.0], focal)
    else:
        fill_box(c, [0.0, 0.0, 792.0, 612.0], navy)

    stamp_icon(c, 'cover_scrim.png', [0.0, 0.0, 792.0, 153.4])

    # left PROPOSAL bar (orange cap + navy) with rotated label
    fill_box(c, [0.0, 0.0, 22.3, 5.4], orange)
    fill_box(c, [0.0, 5.4, 22.3, 225.0], navy)
    c.saveState()
    c.translate(15.4, ry(216.0))
    c.rotate(90)
    t = c.beginText(0, 0)
    t.setFont('FRL', 9)
    t.setFillColorRGB(1, 1, 1)
    t.setCharSpace(2.2)
    t.textOut('PROPOSAL')
    c.drawText(t)
    c.restoreState()

    # title + address (white)
    cell_text(c, 54.0, 0, 41.84, d.get('property_name', d.get('property', '')),
              'FRL', 40, (1, 1, 1), 'left', pad=0)
    cell_text(c, 54.0, 0, 102.74, d.get('address', ''), 'FRL-Med', 14,
              (1, 1, 1), 'left', pad=0)

    # bottom logo box (orange cap + navy) + white M&M logo
    fill_box(c, [310.5, 554.4, 481.5, 558.0], orange)
    fill_box(c, [310.5, 558.0, 481.5, 612.0], navy)
    stamp_icon(c, 'brand/mm_logo_white.png', [320.0, 571.5, 470.0, 596.5], fit=True)


def build_plate44(c, d, photo=None, focal=(0.5, 0.5)):
    """Rent Comps Charts — two stacked comp blocks per page."""
    running_head(c, 'RENT COMPS CHARTS // ', d.get('property', 'SUBJECT PROPERTY'))
    if d.get('top'):
        _chart_block(c, 0.0, d['top'])
    if d.get('bottom'):
        _chart_block(c, CHART_ROW_DY, d['bottom'])


# --- inserted pages (not part of the corporate 53) --------------------------
def build_exec_summary(c, d):
    """Executive Summary letter — inserted after Presented By, before the TOC.
    Reuses the house design system; the body flows so variable-length copy and
    the signature block stay together. Numbers in the body must trace to the
    fact sheet (enforced upstream by the copy layer)."""
    navy, orange, ink = hexcol(C['navy']), hexcol(C['orange']), hexcol(C['ink'])

    running_head(c, 'EXECUTIVE SUMMARY // ', d.get('property', 'SUBJECT PROPERTY'))

    # eyebrow (orange, letter-spaced) + right-aligned attention block
    cell_text(c, 36.0, 0, 120.0, d.get('eyebrow', ''), 'FRL', 10.5, orange,
              'left', pad=0, track=0.9)
    ay = 120.0
    for line in d.get('attn', []):
        cell_text(c, 0, 756.0, ay, line, 'FRL', 9.5, ink, 'right', pad=0)
        ay += 13.5

    # salutation (display face)
    cell_text(c, 36.0, 0, 202.0, d.get('salutation', ''), 'FRL', 15, navy, 'left', pad=0)

    # body paragraphs (flow)
    y = 226.0
    for para in d.get('body', []):
        for line in wrap(c, para, 'FRL', 9.5, 720.0):
            cell_text(c, 36.0, 0, y, line, 'FRL', 9.5, ink, 'left', pad=0)
            y += 14.0
        y += 6.0

    # closing + signature
    y += 8.0
    cell_text(c, 36.0, 0, y, d.get('closing', 'Sincerely,'), 'FRL', 10, ink, 'left', pad=0)
    y += 24.0
    cell_text(c, 36.0, 0, y, d.get('signature', ''), 'FRL-Bold', 15, navy, 'left', pad=0)
    y += 20.0
    cell_text(c, 36.0, 0, y, d.get('titles', ''), 'FRL', 9.5, orange, 'left', pad=0, track=0.5)


INSERTS = {'exec_summary': build_exec_summary}
INSERT_META = {'exec_summary': {'footer_section': 'EXECUTIVE SUMMARY'}}


def wrap(c, text, font, size, measure):
    """Greedy wrap using real font metrics."""
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if pdfmetrics.stringWidth(t, font, size) <= measure:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


BUILDERS = {1: build_plate1, 4: build_plate4,
            25: build_plate25, 35: build_plate35, 41: build_plate41,
            37: build_plate37, 38: build_plate37,
            44: build_plate44, 45: build_plate44}


# ---------------------------------------------------------------- assemble
def assemble(config, library, out_path, fonts, assets=None):
    register_fonts(fonts)
    plates = {p['page']: p for p in PACK['pages']}
    writer = PdfWriter()
    log, n = [], 0

    for item in config['order']:
        # Full-template-first: every page defaults to included; the console
        # toggles pages off. Excluded pages are skipped and don't consume a
        # page number, so footers renumber to the surviving set.
        if item.get('include') is False:
            continue

        # inserted pages (Executive Summary, land-specific pages): no corporate
        # library page and no manifest entry — render on a blank page.
        if 'insert' in item:
            name = item['insert']
            n += 1
            section = INSERT_META.get(name, {}).get('footer_section')
            page = PdfWriter().add_blank_page(PAGE_W, PAGE_H)
            buf, c = new_overlay()
            INSERTS[name](c, item.get('data', {}))
            if section:
                draw_footer(c, n, section)
            page.merge_page(finish_overlay(buf, c))
            writer.add_page(page)
            log.append(f'  {n:>3}  INSERT:{name:<16} '
                       f'{(section + " footer") if section else "no footer"}')
            continue

        plate = item['plate']
        meta = plates[plate]
        cls = meta['class']
        n += 1
        section = meta.get('footer_section')

        src = os.path.join(library, f'p{plate:02d}.pdf')
        page = PdfReader(src).pages[0]

        buf, c = new_overlay()
        did = cls

        if cls == 'build' and plate in BUILDERS:
            # nothing from the corporate page survives: start from blank
            page = PdfWriter().add_blank_page(PAGE_W, PAGE_H)
            BUILDERS[plate](c, item.get('data', {}),
                            item.get('photo'), tuple(item.get('focal', (.5, .5))))
            did = 'build'
        else:
            if cls == 'build':
                did = 'build:NO-BUILDER'
                log.append(f'       !! p{plate:02d} has no builder — corporate '
                           f'placeholder passed through')
            # stamping is driven by the bindings, not by the page class: any
            # corporate page with image frames and a bound photo gets one
            boxes = item.get('boxes', [])
            if boxes and item.get('photo'):
                for box in boxes:
                    place(c, item['photo'], box,
                          tuple(item.get('focal', (.5, .5))))
                did += f'+stamp x{len(boxes)}'

        if section:
            draw_footer(c, n, section)

        page.merge_page(finish_overlay(buf, c))
        writer.add_page(page)
        log.append(f'  {n:>3}  p{plate:02d}  {did:<24} '
                   f'{(section + " footer") if section else "no footer"}')

    tmp = out_path + '.raw'
    with open(tmp, 'wb') as f:
        writer.write(f)
    rc = os.system(f'qpdf --object-streams=generate --recompress-flate '
                   f'--compression-level=9 "{tmp}" "{out_path}" 2>/dev/null')
    if rc == 0:
        os.remove(tmp)
    else:
        os.replace(tmp, out_path)
    return n, log


if __name__ == '__main__':
    cfg = json.load(open(sys.argv[1], encoding='utf-8'))
    n, log = assemble(cfg, sys.argv[2], sys.argv[3], sys.argv[4])
    print('\n'.join(log))
    print(f'\n{n} pages -> {sys.argv[3]} '
          f'({os.path.getsize(sys.argv[3])/1e6:.1f} MB)')
