#!/usr/bin/env python3
"""Run the copy layer's validator against the actual Albemarle draft."""
import sys, json
sys.path.insert(0, '../copy')
import copyfit

# The deal's data sheet — everything the model would be allowed to state.
FACTS = {
    'address': '2202 Albemarle Road, Brooklyn, NY 11226',
    'submarket': 'Flatbush / Prospect Park South',
    'block_lot': 'Block 5126, Lot 33', 'bbl': '3051260033',
    'lot_area_sf': 19522, 'lot_acres': 0.45,
    'frontage_ft': 136.58, 'depth_ft': 142.5,
    'zoning': 'C4-2', 'residential_equivalent': 'R6',
    'far_asofright': 2.20, 'bsf_asofright': 42948,
    'far_uap': 3.90, 'bsf_uap': 76136,
    'bsf_uap_fresh': 85129, 'fresh_grocery_sf': 8993,
    'fresh_min_sf': 6000, 'fresh_cap_sf': 20000,
    'far_commercial': 3.40, 'bsf_commercial': 66375,
    'far_community': 4.80, 'bsf_community': 93706,
    'incremental_bsf': 42181, 'incremental_pct': 98,
    'uap_increment_bsf': 33188,
    'list_price': 16000000, 'list_psf_bsf': 188,
    'comp_range_low': 120, 'comp_range_high': 163,
    'floor_low': 5400000, 'floor_high': 6000000,
    'uap_only_low': 9900000, 'uap_only_high': 11800000,
    'occupancy': '100% vacant', 'building_class': 'Z9',
    # regulatory citations count as facts the broker supplies and must source
    'zr_citations': ['ZR §23-22', 'ZR §24-11'],
    'coy_effective': '12/5/2024',
    'community_district': 14, 'council_district': 40, 'school_district': 17,
    'comps': [
        {'address':'224-240 Clarkson Avenue','price':20000000,'psf':133,'bsf':150300,'date':'Jul 2025'},
        {'address':'885 Rogers Avenue','price':11750000,'psf':163,'bsf':72060,'date':'Oct 2018'},
        {'address':'1070 Flatbush Avenue','price':7400000,'psf':120,'bsf':61320,'date':'Aug 2021'},
    ],
}

# Verbatim from the draft's executive summary.
DRAFT = {
 'description': [
  'The Anton Group at Marcus & Millichap ("M&M") is pleased to present this Broker '
  'Opinion of Value for 2202 Albemarle Road (the "Property"), a 19,522 SF vacant, '
  'as-of-right development site on Albemarle Road in the Flatbush / Prospect Park '
  'South section of Brooklyn.',
  'Zoned C4-2 (plain R6 residential equivalent), the Property is delivered fully '
  'vacant — no existing structure, no demolition, no relocation — and permits '
  'commercial, residential, community facility, or mixed-use development as-of-right. '
  'Confirmed against the current Zoning Resolution (§23-22, as amended by City of Yes '
  'for Housing Opportunity, 12/5/2024), the as-of-right residential base is 42,948 '
  'buildable SF (2.20 FAR); the City of Yes Universal Affordability Preference (UAP) '
  'expands the envelope to 76,136 buildable SF (3.90 FAR). Stacking the site\'s '
  'separate FRESH Zone grocery bonus on top of the UAP base pushes the fully-bonused '
  'envelope to 85,129 buildable SF — the basis for our list price.',
 ],
 'highlights': [
  'Highest & best use is mixed-use multifamily with a grocery-anchored ground floor',
  'Three verified Brooklyn C4-2 / R6-corridor trades bracket $120–$163 per buildable SF',
  'Fact-checked density of 85,129 BSF — +42,181 SF, or +98%, over the as-of-right base',
  'List at $16,000,000, approximately $188 per buildable SF',
 ],
}

b = copyfit.budget()
print('PLATE 25 BUDGET (multifamily property summary)')
print(f"  description target {b['description']['target_chars']} ch, "
      f"max {b['description']['hard_max_chars']} ch")
print(f"  highlights target {b['highlights']['target_chars']} ch, "
      f"{b['highlights']['count'][0]}-{b['highlights']['count'][1]} bullets")

dchars = sum(len(p) for p in DRAFT['description'])
hchars = sum(len(h) for h in DRAFT['highlights'])
print(f"\nALBEMARLE EXEC SUMMARY (abridged to 2 of 4 paragraphs)")
print(f"  description {dchars} ch  -> {dchars/b['description']['target_chars']:.1f}x the plate 25 budget")
print(f"  highlights  {hchars} ch  -> {hchars/b['highlights']['target_chars']:.1f}x")
print(f"  full page in the draft is 3,021 ch -> "
      f"{3021/b['description']['target_chars']:.1f}x")

print('\nVALIDATOR against the real deal sheet:')
problems = copyfit.check(DRAFT, FACTS)
if not problems:
    print('  clean — every figure traces to FACTS')
for p in problems:
    tag = 'FIT   ' if ('flow' in p or 'fill' in p or 'highlight' in p) else 'FACT  '
    print(f'  {tag}— {p}')

print('\nsame copy, one figure corrupted (85,129 -> 91,400 BSF):')
bad = json.loads(json.dumps(DRAFT).replace('85,129', '91,400'))
for p in copyfit.check(bad, FACTS):
    if 'unsupported' in p:
        print(f'  FACT  — {p}')
