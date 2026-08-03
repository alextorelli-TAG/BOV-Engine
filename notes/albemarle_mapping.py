#!/usr/bin/env python3
"""Map each page of the Albemarle draft onto the corporate plate inventory."""
import json, pdfplumber

PACK = json.load(open('../compile/bov_template_pack.json'))
LABEL = {1:'Cover',3:'Presented By',4:'Table of Contents',5:'Div — M&M Advantage',
 14:'Making a Market',17:'Capital Migration',19:'Div — Advisor Bios',20:'Advisor Bio',
 24:'Div — Investment Overview',25:'Property Summary',27:'Local Map',
 30:'Div — Financial Analysis',31:'Financial Detail',33:'Div — Sale Comparables',
 35:'Sale Comps Summary',47:'Metro Overview'}

# draft page -> (corporate plate or None, verdict, note)
MAP = [
 (1,  1,   'maps',    'Cover. Corporate layout is landscape with full-bleed photo.'),
 (2,  3,   'maps',    'Presented By. Corporate carries one advisor; this shows two.'),
 (3,  4,   'maps',    'Contents. Generated from the plate selection either way.'),
 (4,  None,'NEW',     'Executive Summary. The 53-plate template has no such page.'),
 (5,  24,  'maps',    'Section divider.'),
 (6,  25,  'partial', 'Site & zoning facts. Corporate offering summary is NOI/cap/GRM/price-per-unit — none exist for land.'),
 (7,  27,  'partial', 'Location + transit table. Closest corporate plate is the local map; the transit list has no frame.'),
 (8,  30,  'maps',    'Section divider, relabelled.'),
 (9,  None,'NEW',     'Five zoning pathways. No corporate equivalent.'),
 (10, 31,  'partial', 'Valuation scenarios. Corporate plate 31 is an empty chart frame — usable as a host.'),
 (11, None,'NEW',     'Strategies reconciled. No corporate equivalent.'),
 (12, 33,  'maps',    'Section divider.'),
 (13, 35,  'partial', 'Land comps. Corporate columns are price/bldg SF/price-per-unit/cap/units; land needs BSF, $/BSF, zoning.'),
 (14, 5,   'maps',    'Section divider.'),
 (15, None,'NEW',     'Anton Group select experience. Team track record — variant, built once.'),
 (16, 17,  'partial', '1031 exchange. Corporate covers exchange capital but has no timeline page.'),
 (17, 19,  'maps',    'Section divider.'),
 (18, 20,  'maps',    'Advisor bio — Anton.'),
 (19, 20,  'maps',    'Advisor bio — Kessler.'),
]

with pdfplumber.open('../../alb.pdf') as pdf:
    chars = {i+1: len(pdf.pages[i].extract_text() or '') for i in range(19)}

print(f"{'draft':>5} {'plate':>6}  {'verdict':<8} {'ch':>5}  note")
print('-' * 108)
tally = {}
for d, c, v, note in MAP:
    tally[v] = tally.get(v, 0) + 1
    plate = f"p{c:02d}" if c else "—"
    print(f"{d:>5} {plate:>6}  {v:<8} {chars[d]:>5}  {note}")

print('-' * 108)
print('verdict tally:', tally)

reusable = [c for d, c, v, note in MAP if v == 'maps']
print(f"\nreuses {len(reusable)} corporate plates unchanged: "
      f"{', '.join('p%02d' % c for c in sorted(set(reusable)))}")
print(f"needs {tally.get('NEW',0)} genuinely new plates and "
      f"{tally.get('partial',0)} land-specific variants of existing ones")

# what the corporate offering-summary table demands vs what a land deal has
mf = ['Listing Price','NOI','Cap Rate','GRM','Total Return %','Price/SF','Rent/SF','Price/Unit']
land = ['List Price','Lot Area','Zoning','As-of-Right FAR','Bonused FAR',
        'Buildable SF','$/BSF','Delivery']
print('\ncorporate plate 25 offering summary rows:')
print('  ', ' · '.join(mf))
print('what 2202 Albemarle actually has:')
print('  ', ' · '.join(land))
print('\noverlap: Listing Price only.')
