#!/usr/bin/env python3
"""Google Maps rendering for the comps map plates (34 Sale, 40 Rent).

Server-side only. Geocodes the subject + comp addresses and fetches a branded
Static Maps PNG with numbered pins, cached to disk so repeat builds don't re-bill.
The API key is read from the environment (GOOGLE_MAPS_API_KEY, loaded from .env by
serve/app.py) — it never reaches the browser, the config JSON, or the logs.

Everything degrades gracefully: no key, a failed geocode, or a network error
returns None, and the caller falls back to the corporate placeholder.
"""
import hashlib
import json
import os

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
MAPS_DIR = os.path.join(CACHE, 'maps')
GEO_CACHE = os.path.join(CACHE, 'geocode.json')

GEOCODE_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
STATIC_URL = 'https://maps.googleapis.com/maps/api/staticmap'

# Muted, book-matching map style: POIs/transit off, soft land/water, white roads,
# so the navy/orange pins are the only thing that reads loudly.
BRAND_STYLE = [
    'feature:poi|visibility:off',
    'feature:transit|visibility:off',
    'feature:road|element:labels|visibility:simplified',
    'feature:administrative|element:labels.text.fill|color:0x556070',
    'feature:landscape|color:0xeef0f2',
    'feature:road|element:geometry|color:0xffffff',
    'feature:road.arterial|element:geometry|color:0xe4e7ea',
    'feature:water|color:0xc3ccd6',
]
SUBJECT_COLOR = '0xF58026'   # orange
COMP_COLOR = '0x002B5C'      # navy
MAX_EDGE = 640               # Static Maps free-tier cap per side (scale=2 -> 2x px)


# Accept either the operator's existing name or the generic one.
KEY_NAMES = ('GMAPS_PLATFORM_API_KEY', 'GOOGLE_MAPS_API_KEY')


def _key():
    for name in KEY_NAMES:
        v = os.environ.get(name, '').strip()
        if v:
            return v
    return ''


def _load_geo():
    try:
        with open(GEO_CACHE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_geo(cache):
    os.makedirs(CACHE, exist_ok=True)
    with open(GEO_CACHE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=0)


def geocode(address):
    """Return (lat, lng) for an address, or None. Cached on disk by address."""
    key = _key()
    if not key or not address or not address.strip():
        return None
    norm = ' '.join(address.split()).lower()
    cache = _load_geo()
    if norm in cache:                       # cached (may be null for a prior miss)
        v = cache[norm]
        return tuple(v) if v else None
    try:
        r = httpx.get(GEOCODE_URL, params={'address': address, 'key': key}, timeout=15)
        data = r.json()
        if data.get('status') == 'OK' and data.get('results'):
            loc = data['results'][0]['geometry']['location']
            coord = [loc['lat'], loc['lng']]
        else:
            coord = None
    except Exception:
        return None                          # transient error: don't poison cache
    cache[norm] = coord
    _save_geo(cache)
    return tuple(coord) if coord else None


def _frame_size(w_pt, h_pt):
    """Static Maps size (<=640 per side) matching the frame's aspect ratio."""
    if w_pt >= h_pt:
        w, h = MAX_EDGE, max(1, round(MAX_EDGE * h_pt / w_pt))
    else:
        h, w = MAX_EDGE, max(1, round(MAX_EDGE * w_pt / h_pt))
    return min(w, MAX_EDGE), min(h, MAX_EDGE)


def build_static_map(subject_address, comps, w_pt, h_pt):
    """Render the comps map PNG and return its cached path, or None.

    comps: list of {label, address}. Subject is an orange 'S' pin; comps are navy
    numbered pins in the given label order (matches the summary table).
    """
    if not _key():
        return None

    subj = geocode(subject_address) if subject_address else None
    pins = []
    for c in (comps or []):
        ll = geocode(c.get('address'))
        if ll:
            lab = str(c.get('label', '')).strip()[-1:] or '1'   # single char
            pins.append((lab, ll))
    if not subj and not pins:
        return None

    w, h = _frame_size(w_pt, h_pt)
    # Comps first, subject last, so the orange subject pin always draws on top.
    markers = [f'color:{COMP_COLOR}|label:{lab}|{ll[0]},{ll[1]}' for lab, ll in pins]
    if subj:
        markers.append(f'color:{SUBJECT_COLOR}|label:S|{subj[0]},{subj[1]}')

    # Cache key over everything that changes the image — but NOT the API key, so a
    # rotated key still reuses cached tiles.
    sig = json.dumps({'size': [w, h], 'style': BRAND_STYLE, 'markers': markers},
                     sort_keys=True)
    name = hashlib.sha1(sig.encode()).hexdigest()[:16] + '.png'
    out = os.path.join(MAPS_DIR, name)
    if os.path.isfile(out):
        return out

    params = [('size', f'{w}x{h}'), ('scale', '2'), ('format', 'png'),
              ('maptype', 'roadmap'), ('key', _key())]
    params += [('style', s) for s in BRAND_STYLE]
    params += [('markers', m) for m in markers]
    try:
        r = httpx.get(STATIC_URL, params=params, timeout=20)
    except Exception:
        return None
    if r.status_code != 200 or not r.content.startswith(b'\x89PNG'):
        return None
    os.makedirs(MAPS_DIR, exist_ok=True)
    with open(out, 'wb') as f:
        f.write(r.content)
    return out
