#!/usr/bin/env python3
"""Scan the committed image assets and emit assemble/assets/asset_catalog.json.

The console (studio/tag_bov_studio.html) fetches this catalog via the build
server (GET /api/assets) and shows every image as a preloaded, bindable thumbnail
— the "pick, don't upload" model. Re-run whenever assets change:

    python tools/build_asset_catalog.py

Slot inference mirrors the console's own guessSlot()/CORPORATE_LINKS rules so the
same filenames land in the same slots the assembler expects.
"""
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assemble', 'assets')
CATALOG = os.path.join(ASSETS, 'asset_catalog.json')

WEB_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
ASSET_CLASSES = {'multifamily', 'office', 'retail', 'industrial', 'mixeduse', 'devsite'}

# Byte-for-byte the console's CORPORATE_LINKS crosswalk (lowercased filenames).
CORPORATE_LINKS = {
    'gettyimages-583904061.jpg': 'divider_bg',
    'template1_cover1.jpg': 'property_photo',
    'mm_headshot3_4x5.jpg': 'advisor_headshot',
    'mm_logo2018_blue295_large.png': 'brand_logo',
    'background.jpg': 'marketing_bg',
}


def guess_slot(fname, folder):
    """Infer the named template slot for a file, folder-aware."""
    n = fname.lower()
    if n in CORPORATE_LINKS:
        return CORPORATE_LINKS[n]
    if folder == 'brand':
        return 'brand_logo'
    if folder == 'headshots':
        return 'advisor_headshot'
    if folder.startswith('stock/dividers') or folder == 'stock/textures':
        return 'divider_bg'
    # stock/corporate and anything else: keyword rules, then corporate default
    if any(k in n for k in ('headshot', 'portrait', '_4x5')):
        return 'advisor_headshot'
    if any(k in n for k in ('divider', 'palm', 'skyline', 'aerial')):
        return 'divider_bg'
    if 'logo' in n:
        return 'brand_logo'
    if 'background' in n or 'backround' in n:
        return 'marketing_bg'
    return 'corporate_stock'


def prettify(stem):
    return stem.replace('_', ' ').replace('-', ' ').strip().title()


def scan():
    items = []
    # (folder-relative-to-assets, on-disk dir)
    roots = [
        ('brand', os.path.join(ASSETS, 'brand')),
        ('headshots', os.path.join(ASSETS, 'headshots')),
        ('stock/corporate', os.path.join(ASSETS, 'stock', 'corporate')),
        ('stock/textures', os.path.join(ASSETS, 'stock', 'textures')),
    ]
    # asset-class divider subfolders
    div_root = os.path.join(ASSETS, 'stock', 'dividers')
    if os.path.isdir(div_root):
        for sub in sorted(os.listdir(div_root)):
            p = os.path.join(div_root, sub)
            if os.path.isdir(p):
                roots.append(('stock/dividers/' + sub, p))

    for folder, d in roots:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in WEB_EXT:
                continue
            path = os.path.join(d, fname)
            try:
                with Image.open(path) as im:
                    w, h = im.size
            except Exception:
                continue  # unreadable / non-image
            rel = f'assemble/assets/{folder}/{fname}'.replace('\\', '/')
            slot = guess_slot(fname, folder)
            asset_class = None
            if folder.startswith('stock/dividers/'):
                cand = folder.split('/', 2)[2]
                if cand in ASSET_CLASSES:
                    asset_class = cand
            item = {
                'id': rel.replace('/', '_').replace('.', '_'),
                'file': rel,                                    # build-time path (server resolves)
                'url': f'/assets/{folder}/{fname}',             # browser thumbnail URL
                'slot': slot,
                'label': prettify(os.path.splitext(fname)[0]),
                'w': w, 'h': h,
            }
            if asset_class:
                item['assetClass'] = asset_class
            items.append(item)
    return items


def main():
    items = scan()
    with open(CATALOG, 'w', encoding='utf-8') as f:
        json.dump({'assets': items}, f, indent=2)
    by_slot = {}
    for it in items:
        by_slot[it['slot']] = by_slot.get(it['slot'], 0) + 1
    print(f'wrote {CATALOG} with {len(items)} assets')
    for slot, n in sorted(by_slot.items()):
        print(f'  {slot:<18} {n}')


if __name__ == '__main__':
    main()
