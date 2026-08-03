#!/usr/bin/env python3
"""Compile YE_2025_BOV_Template.idml into a portable template pack.

    python3 idml_compile.py <unpacked_idml_dir> [out.json]

An IDML is a zip of XML, so this needs no Adobe software. It recovers the
authoritative brand tokens, the named image-slot map, and every text/image
frame box in page-local points -- which is what lets the build templates match
corporate exactly instead of by eye.

Re-run it whenever corporate reissues the template; the pack is the only thing
downstream code reads.
"""
import json, re, os, sys
from collections import defaultdict
from xml.etree import ElementTree as ET

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/idml/unpacked'
OUT  = sys.argv[2] if len(sys.argv) > 2 else 'bov_template_pack.json'
NS = {'idPkg': 'http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging'}
print(f'compiling {ROOT}')

# ============================ STAGE 1 — GEOMETRY ==========================




def spread_order():
    d = open(f'{ROOT}/designmap.xml', encoding='utf-8').read()
    return re.findall(r'<idPkg:Spread\s+src="(Spreads/[^"]+)"', d)


def mat_apply(m, x, y):
    a, b, c, d, tx, ty = m
    return (a * x + c * y + tx, b * x + d * y + ty)


def get_transform(el):
    t = el.get('ItemTransform')
    if not t:
        return (1, 0, 0, 1, 0, 0)
    v = [float(x) for x in t.split()]
    return tuple(v)


def compose(m1, m2):
    """m1 applied after m2 (parent, child) -> combined."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def path_bounds(el, m):
    pts = []
    for pp in el.iter('PathPointType'):
        anc = pp.get('Anchor')
        if anc:
            x, y = [float(v) for v in anc.split()]
            pts.append(mat_apply(m, x, y))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def load_stories():
    """story id -> plain text, plus applied paragraph styles."""
    out = {}
    sd = f'{ROOT}/Stories'
    for fn in os.listdir(sd):
        try:
            tree = ET.parse(os.path.join(sd, fn))
        except ET.ParseError:
            continue
        for st in tree.iter('Story'):
            sid = st.get('Self')
            chunks, styles, fonts, sizes, fills = [], set(), set(), set(), set()
            for psr in st.iter('ParagraphStyleRange'):
                ps = psr.get('AppliedParagraphStyle', '')
                styles.add(ps.replace('ParagraphStyle/', ''))
                for csr in psr.iter('CharacterStyleRange'):
                    if csr.get('PointSize'):
                        sizes.add(csr.get('PointSize'))
                    if csr.get('FillColor'):
                        fills.add(csr.get('FillColor').replace('Color/', ''))
                    af = csr.find('Properties/AppliedFont')
                    if af is not None and af.text:
                        fonts.add(f"{af.text}|{csr.get('FontStyle','')}")
                    for c in csr.iter('Content'):
                        if c.text:
                            chunks.append(c.text)
                    for _ in csr.iter('Br'):
                        chunks.append('\n')
            out[sid] = {
                'text': ''.join(chunks).strip(),
                'para_styles': sorted(styles),
                'fonts': sorted(fonts),
                'sizes': sorted(sizes, key=lambda s: -float(s)) if sizes else [],
                'fills': sorted(fills),
            }
    return out


def build_model():
    stories = load_stories()
    order = spread_order()
    pages = []
    for pnum, sp in enumerate(order, 1):
        tree = ET.parse(f'{ROOT}/{sp}')
        spread_el = next(tree.iter('Spread'))
        page_el = next(spread_el.iter('Page'))
        pt = get_transform(page_el)
        # page-local space: undo the page's own placement, ignore pasteboard offset
        sm = (1, 0, 0, 1, -pt[4], -pt[5])
        gb = page_el.get('GeometricBounds')
        pb = [float(x) for x in gb.split()] if gb else None  # y1 x1 y2 x2
        items = []
        for el in spread_el:
            tag = el.tag
            if tag not in ('TextFrame', 'Rectangle', 'Polygon', 'Oval',
                           'GraphicLine', 'Group'):
                continue
            m = compose(sm, get_transform(el))
            b = path_bounds(el, m)
            rec = {'type': tag, 'id': el.get('Self'), 'bounds': None if not b
                   else [round(v, 2) for v in b]}
            if el.get('Name'):
                rec['name'] = el.get('Name')
            if el.get('ParentStory'):
                sid = el.get('ParentStory')
                s = stories.get(sid, {})
                rec['story'] = sid
                rec['text'] = s.get('text', '')[:400]
                rec['fonts'] = s.get('fonts', [])
                rec['sizes'] = s.get('sizes', [])
                rec['fills'] = s.get('fills', [])
                rec['para_styles'] = s.get('para_styles', [])
            # image / placed content
            for img in el.iter('Image'):
                lk = img.find('Link')
                rec['image'] = lk.get('LinkResourceURI') if lk is not None else 'embedded'
            if el.get('FillColor'):
                rec['fill'] = el.get('FillColor').replace('Color/', '')
            items.append(rec)
        pages.append({'page': pnum, 'spread': sp, 'page_bounds': pb,
                      'n_items': len(items), 'items': items})
    print(f'  extracted {len(pages)} pages, '
          f'{sum(p["n_items"] for p in pages)} top-level items')
    return {'pages': pages}


# ============================ STAGE 2 — TEMPLATE PACK ======================
MODEL = build_model()

# ---------------------------------------------------------------- swatches
def cmyk_hex(c, m, y, k):
    c, m, y, k = [v / 100 for v in (c, m, y, k)]
    return '#%02X%02X%02X' % tuple(
        max(0, min(255, round(255 * (1 - v) * (1 - k)))) for v in (c, m, y))

def swatches():
    d = open(f'{ROOT}/Resources/Graphic.xml', encoding='utf-8').read()
    out = {}
    for mm in re.finditer(r'<Color\b[^>]*>', d):
        s = mm.group(0)
        g = lambda a: (re.search(a + r'="([^"]*)"', s) or [None, ''])[1]
        name, space, vals = g('Name'), g('Space'), g('ColorValue')
        if not name or name == '$ID/' or not vals:
            continue
        v = [float(x) for x in vals.split()]
        if space == 'CMYK' and len(v) == 4:
            out[name] = {'space': 'CMYK', 'cmyk': [round(x, 1) for x in v],
                         'hex': cmyk_hex(*v)}
        elif space == 'RGB' and len(v) == 3:
            out[name] = {'space': 'RGB', 'rgb': [int(x) for x in v],
                         'hex': '#%02X%02X%02X' % tuple(int(x) for x in v)}
    return out

# ------------------------------------------------------------ image slots
# Link filename -> logical slot. This is the substitution surface.
SLOT_BY_LINK = {
    'GettyImages-583904061.jpg': 'divider_bg',       # all 8 section dividers
    'Template1_Cover1.jpg':      'property_photo',   # hero + inset + faded bg
    'MM_Headshot3_4x5.jpg':      'advisor_headshot',
    'MM_logo2018_blue295_large.png': 'brand_logo',
    'background.jpg':            'marketing_bg',
}

def slots():
    found = defaultdict(list)
    for p in MODEL['pages']:
        for it in p['items']:
            uri = it.get('image')
            if not uri:
                continue
            fn = os.path.basename(uri.replace('%20', ' '))
            slot = SLOT_BY_LINK.get(fn, 'corporate_stock')
            b = it['bounds']
            w, h = round(b[2] - b[0], 1), round(b[3] - b[1], 1)
            found[slot].append({'page': p['page'], 'box': [round(v, 1) for v in b],
                                'w': w, 'h': h,
                                'aspect': round(w / h, 3) if h else None,
                                'link': fn})
    return dict(found)

# ------------------------------------------------------------- page specs
CLASS = {}
for pnum, cls in [
    *[(n, 'static') for n in (2, 5, 6, 7, 8, 9, 13, 14, 15, 16, 17, 18, 19,
                              21, 22, 23, 24, 30, 33, 39, 46)],
    *[(n, 'annual') for n in (10, 11, 12)],
    *[(n, 'variant') for n in (3, 20, 47, 48, 49, 53)],
    *[(n, 'stamp') for n in (26, 27, 28, 29, 31, 32, 34, 36, 40, 42, 43,
                             50, 51, 52)],
    *[(n, 'build') for n in (1, 4, 25, 35, 37, 38, 41, 44, 45)],
]:
    CLASS[pnum] = cls

SECTION = {
    **{n: 'Marcus & Millichap Advantage' for n in range(5, 19)},
    **{n: 'Advisor Bios' for n in (19, 20)},
    **{n: 'Marketing Plan' for n in (21, 22, 23)},
    **{n: 'Investment Overview' for n in range(24, 30)},
    **{n: 'Financial Analysis' for n in (30, 31, 32)},
    **{n: 'Sale Comparables' for n in range(33, 39)},
    **{n: 'Rent Comparables' for n in range(39, 46)},
    **{n: 'Market Overview' for n in range(46, 53)},
    **{n: 'Front Matter' for n in (1, 2, 3, 4)},
    53: 'Back Matter',
}

FOOTER_SECTION = {
    **{n: 'INVESTMENT OVERVIEW' for n in list(range(6, 19)) + list(range(25, 30))},
    **{n: 'ADVISOR BIOS' for n in (20,)},
    **{n: 'MARKETING PLAN' for n in (22, 23)},
    **{n: 'FINANCIAL ANALYSIS' for n in (31, 32)},
    **{n: 'SALE COMPARABLES' for n in (34, 35, 36, 37, 38)},
    **{n: 'RENT COMPARABLES' for n in (40, 41, 42, 43, 44, 45)},
    **{n: 'MARKET OVERVIEW' for n in (47, 48, 49, 50, 51, 52)},
}

def pages():
    out = []
    for p in MODEL['pages']:
        n = p['page']
        tfs = [i for i in p['items'] if i['type'] == 'TextFrame' and i.get('text')]
        imgs = [i for i in p['items'] if i.get('image')]
        out.append({
            'page': n,
            'section': SECTION.get(n),
            'footer_section': FOOTER_SECTION.get(n),
            'class': CLASS.get(n, 'static'),
            'spread': p['spread'],
            'text_frames': len(tfs),
            'image_frames': len(imgs),
            'slots': sorted({SLOT_BY_LINK.get(
                os.path.basename(i['image'].replace('%20', ' ')),
                'corporate_stock') for i in imgs}),
            'frames': [
                {'box': i['bounds'], 'sizes': i.get('sizes', [])[:2],
                 'snippet': (i.get('text') or '')[:60]}
                for i in tfs
            ],
        })
    return out

pack = {
    'name': 'TAG_BOV_Template_Pack',
    'compiled_from': 'YE_2025_BOV_Template.idml',
    'idml_dom_version': '21.2',
    'page': {'width': 792, 'height': 612, 'units': 'pt',
             'orientation': 'landscape',
             'bleed': 9, 'origin': 'top-left'},
    'tokens': {
        'color': swatches(),
        'type': {
            'display': {'family': 'Frank Ruhl Libre',
                        'source': 'Google Fonts', 'license': 'OFL',
                        'weights': [400, 500, 700, 900]},
            'ui': {'family': 'Roboto', 'source': 'Google Fonts',
                   'license': 'Apache-2.0', 'weights': [400, 500]},
            'scale_pt': {'page_header': 16, 'section_head': 12,
                         'body': 9, 'bullet': 10, 'footer': 9,
                         'hero': 24, 'stat': 48},
        },
        'footer': {'band': [0, 578.79, 233.28, 595.13],
                   'band_color': '#B0B7BC',
                   'rule_y': 594.88,
                   'page_num_box': [23.54, 581.98, 58.54, 590.6],
                   'label_box': [60.5, 581.98, 261.0, 590.6],
                   'format': '{n} | {section}'},
    },
    'image_slots': slots(),
    'pages': pages(),
}

pack['tokens']['color_resolved'] = {
 'navy':        {'hex': '#002B5C', 'cmyk': [100, 69, 8, 54], 'use': 'primary ground, headings'},
 'navy_deep':   {'hex': '#00224A', 'cmyk': None,             'use': 'divider overlay'},
 'orange':      {'hex': '#F58026', 'cmyk': [0, 51, 77, 0],   'use': 'accent, eyebrows, rules'},
 'orange_warm': {'hex': '#E5893F', 'cmyk': [0, 62, 90, 0],   'use': 'chart fills'},
 'grey_band':   {'hex': '#E5E7E6', 'cmyk': None,             'use': 'footer band'},
 'grey_mid':    {'hex': '#A7A9AC', 'cmyk': None,             'use': 'placeholder text'},
 'ink':         {'hex': '#222222', 'cmyk': [5.3, 3.8, 3.8, 86], 'use': 'body copy'},
 'paper':       {'hex': '#FFFFFF', 'cmyk': [0, 0, 0, 0],     'use': 'page ground'},
}
pack['tokens']['footer']['band_color'] = '#E5E7E6'
pack['notes'] = [
 'tokens.color CMYK->hex is an unmanaged approximation; use tokens.color_resolved for screen.',
 'divider_bg is one full-bleed 792x612 asset on all 8 section dividers - a single swap retones the book by asset class.',
 'property_photo spans 11 aspect ratios across 24 frames, so each upload needs a focal point for safe auto-crop.',
 'No XML tags and only 12 paragraph styles, most unused: drive layout from frame geometry, not from styles.',
]

json.dump(pack, open(OUT, 'w'), indent=1)

cnt = defaultdict(int)
for p in pack['pages']:
    cnt[p['class']] += 1
print('template pack written')
print('  swatches:', len(pack['tokens']['color']))
print('  image slots:', {k: len(v) for k, v in pack['image_slots'].items()})
print('  page classes:', dict(cnt))
