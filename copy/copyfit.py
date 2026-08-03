#!/usr/bin/env python3
"""Copy layer for the BOV pipeline.

Three jobs, in order:

  1. budget()   - work out how much copy each frame can physically hold,
                  from the compiled IDML geometry rather than from a guess
  2. prompt()   - build a generation request bounded by that budget
  3. check()    - refuse output that overflows the frame or states a number
                  the source data doesn't support

The model never sees a blank page. It sees a fact sheet, the broker's raw
notes, and a character ceiling. It rewrites; it does not author.
"""
import json, re, math

PACK = json.load(open(__import__('os').path.join(__import__('os').path.dirname(__file__),'bov_template_pack.json')))

# Calibrated against the template's own copy: 12 full lines of 9pt Frank Ruhl
# Libre in a 349pt measure averaged 85.8 characters. That is 0.452 em of
# advance per character. Bullets carry a hanging indent, so they get less room.
EM_PER_CHAR = 0.452
BULLET_INDENT = 12.0


def frame(page, index=0):
    p = next(x for x in PACK['pages'] if x['page'] == page)
    return p['frames'][index]['box']


def capacity(box, pt, leading, indent=0.0):
    """Lines available and characters per line for a frame."""
    w = (box[2] - box[0]) - indent
    h = box[3] - box[1]
    return {
        'lines': int(h // leading),
        'chars_per_line': int(w / (pt * EM_PER_CHAR)),
        'width_pt': round(w, 1), 'height_pt': round(h, 1),
    }


def estimate_lines(text, chars_per_line, is_bullets=False):
    """Wrap-aware line count. The renderer is the source of truth; this is
    only accurate enough to steer the generation loop."""
    n = 0
    blocks = text if isinstance(text, list) else text.split('\n')
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        n += max(1, math.ceil(len(b) / chars_per_line))
    return n


# --------------------------------------------------------------- budgets
def budget():
    """Plate 25 carries the entire per-property copy load. Its description and
    highlights share one frame, so they compete for the same 26 lines."""
    box = frame(25, 0)                       # [36.0, 124.6, 384.8, 495.5]
    body = capacity(box, 9, 14)
    bull = capacity(box, 10, 16, BULLET_INDENT)
    heads = 2                                # PROPERTY DESCRIPTION / HIGHLIGHTS
    gaps = 2                                 # space above each head
    total = body['lines']
    return {
        'frame': box,
        'total_lines': total,
        'reserved_lines': heads + gaps,
        'description': {
            'lines': 15,
            'chars_per_line': body['chars_per_line'],
            'target_chars': 15 * body['chars_per_line'],
            'hard_max_chars': 16 * body['chars_per_line'],
            'paragraphs': [3, 4],
        },
        'highlights': {
            'lines': total - 15 - heads - gaps,
            'chars_per_line': bull['chars_per_line'],
            'count': [4, 6],
            'chars_each': [45, 95],
            'target_chars': 440,
        },
    }


# ---------------------------------------------------------------- prompt
SCHEMA = {
    'property_name': 'str — how the asset is titled on the cover',
    'description': ['str', '...'],   # 3-4 paragraphs
    'highlights': ['str', '...'],    # 4-6 bullets, no terminal period
}

RULES = """\
- Write in the register of the supplied house samples. Declarative, specific,
  no adjectives that could apply to any building.
- Every figure you state must appear in FACTS verbatim. State no number that
  is not there. Do not round, recompute, or infer.
- The investment thesis comes from NOTES. Do not invent a reason the asset is
  attractive; sharpen the one you are given.
- No superlatives that cannot be sourced ("best in class", "unmatched").
- No forward-looking rent claims. Compliance rejects them.
- Final paragraph states the offering terms exactly as given.
"""


def prompt(facts, notes, samples, b=None):
    b = b or budget()
    d, h = b['description'], b['highlights']
    return f"""You are drafting the property summary for a Marcus & Millichap
Broker's Opinion of Value. Return JSON only, matching this shape:

{json.dumps(SCHEMA, indent=2)}

LENGTH IS A HARD CONSTRAINT. The frame is {b['frame'][2]-b['frame'][0]:.0f}pt
wide and holds {b['total_lines']} lines total.

  description: {d['paragraphs'][0]}-{d['paragraphs'][1]} paragraphs,
               {d['target_chars']} characters total, {d['hard_max_chars']} absolute maximum.
  highlights:  {h['count'][0]}-{h['count'][1]} bullets,
               {h['chars_each'][0]}-{h['chars_each'][1]} characters each,
               {h['target_chars']} characters total.

Copy that exceeds these overflows the page and is rejected.

RULES
{RULES}
FACTS (the only numbers you may state)
{json.dumps(facts, indent=2)}

NOTES (the broker's thesis — sharpen, do not replace)
{notes}

HOUSE SAMPLES (match this voice)
{chr(10).join('---' + chr(10) + s for s in samples)}
"""


# -------------------------------------------------------------- validate
NUM = re.compile(r'\$?\d[\d,]*\.?\d*%?')


def _canon(tok):
    """Canonical numeric form so 2.20, 2.2 and '2.20' all compare equal."""
    t = tok.strip('$%,. ').replace(',', '')
    if not t:
        return None
    try:
        f = float(t)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return t


def numerals(text):
    return {c for c in (_canon(m.group(0)) for m in NUM.finditer(text)) if c}


def check(out, facts, b=None):
    """Returns [] if the draft is publishable, otherwise the reasons it isn't."""
    b = b or budget()
    problems = []

    desc = '\n'.join(out.get('description', []))
    hl = out.get('highlights', [])

    dl = estimate_lines(out.get('description', []), b['description']['chars_per_line'])
    hlines = estimate_lines(hl, b['highlights']['chars_per_line'], True)
    used = dl + hlines + b['reserved_lines']
    if used > b['total_lines']:
        problems.append(f'overflows frame: ~{used} lines used of {b["total_lines"]} '
                        f'(description {dl}, highlights {hlines})')
    if used < b['total_lines'] - 3:
        problems.append(f'underfills frame: ~{used} of {b["total_lines"]} lines, '
                        f'will leave a visible gap')
    if not (b['highlights']['count'][0] <= len(hl) <= b['highlights']['count'][1]):
        problems.append(f'{len(hl)} highlights, expected '
                        f'{b["highlights"]["count"][0]}-{b["highlights"]["count"][1]}')

    # Every number in the copy must be traceable to the fact sheet. Regulatory
    # citations and dates count as facts, so the sheet must carry them; that is
    # deliberate, since an unsourced statute reference is exactly the kind of
    # thing that should not reach an owner.
    allowed = numerals(json.dumps(facts))
    for n in numerals(desc + ' ' + ' '.join(hl)):
        if n not in allowed and not (n.isdigit() and len(n) <= 2):
            problems.append(f'unsupported figure "{n}" — not present in FACTS')

    for phrase in ('best in class', 'unmatched', 'unparalleled', 'will increase',
                   'guaranteed', 'projected to rise'):
        if phrase in (desc + ' '.join(hl)).lower():
            problems.append(f'non-compliant phrasing: "{phrase}"')

    return problems


# ------------------------------------------------------------------ demo
if __name__ == '__main__':
    b = budget()
    print('PLATE 25 COPY BUDGET, derived from frame geometry')
    print(f"  frame            {b['frame']}  "
          f"({b['frame'][2]-b['frame'][0]:.0f} x {b['frame'][3]-b['frame'][1]:.0f} pt)")
    print(f"  total lines      {b['total_lines']}   "
          f"(headings and spacing take {b['reserved_lines']})")
    print(f"  description      {b['description']['lines']} lines x "
          f"{b['description']['chars_per_line']} ch = "
          f"{b['description']['target_chars']} chars target, "
          f"{b['description']['hard_max_chars']} max")
    print(f"  highlights       {b['highlights']['lines']} lines, "
          f"{b['highlights']['count'][0]}-{b['highlights']['count'][1]} bullets, "
          f"{b['highlights']['target_chars']} chars target")

    # sanity: does the estimator reproduce the template's own copy?
    tmpl_desc = [
      "The Multifamily Best of the Best community is composed of 30 apartment homes in a three story building with rooftop pool. The building was developed in two stages. The first was completed in 1984 and the second in 2005. The property was designed with contemporary architecture and has been meticulously maintained.",
      "The Multifamily Best of the Best encompasses .86 acres. The building is wood frame with a painted stucco exterior and flat, concrete roof. The approximately 26,900 square feet of residential living area consists of 15 one-bedroom/one-bath units, 2 two-bedroom/1.5-bath units, 9 two-bed/two bath units, 3 three-bedroom/two-bath units, and 1 four-bedroom/three bath unit.",
      "The community is in walking distance of Miami Beach's famous entertainment, eateries and schools. The property has strong visual appeal with an impressive amenity package, lush landscaping and the conveniences demanded by today's sophisticated rental market.",
      "The property is being offered for sale at a price of $12,000,000. It can be purchased on an unleveraged all-cash basis or on a leveraged basis with the buyer obtaining a new first loan through a third-party lender.",
    ]
    est = estimate_lines(tmpl_desc, b['description']['chars_per_line'])
    print(f"\n  estimator check: template description -> {est} lines "
          f"(measured in the PDF: 15)")

    print('\nVALIDATOR, against a deliberately bad draft')
    facts = {'price': '$12,000,000', 'units': 30, 'noi': '$512,127', 'cap_rate': '4.27%'}
    bad = {'description': ['A best in class asset offered at $12,000,000 with '
                           'a 5.10% cap rate that will increase over time.'],
           'highlights': ['30 units']}
    for p in check(bad, facts):
        print('  REJECT —', p)
