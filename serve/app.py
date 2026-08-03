#!/usr/bin/env python3
"""BOV build server — the handoff between the console and the assembler.

The console (studio/tag_bov_studio.html) POSTs an assembler config to
`/api/bov/build`; this server runs assemble/assembler.py against it and streams
the finished PDF back. Runs locally for MVP:

    pip install -r serve/requirements.txt
    uvicorn serve.app:app --reload --port 8000

The Anthropic API key (once copy-generation lands, ROADMAP Part D) lives only in
this process's environment — the browser never sees it.
"""
import json
import os
import sys
import tempfile

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# --- wire in the assembler --------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'assemble'))
import assembler  # noqa: E402  (path is set above)

LIBRARY = os.path.join(ROOT, 'page_library')      # corporate p01..p53.pdf
FONTS = os.path.join(ROOT, 'fonts')               # FrankRuhlLibre TTFs
ASSETS = os.path.join(ROOT, 'assemble', 'assets')  # brand / headshots / stock
STUDIO = os.path.join(ROOT, 'studio', 'tag_bov_studio.html')  # the console
CATALOG = os.path.join(ASSETS, 'asset_catalog.json')          # preloaded assets
TEAM = os.path.join(ROOT, 'examples', 'team_the_anton_group.json')

# Where operator-supplied images (the "Linked" folder, property photos) live.
# The console emits repo-relative paths (from the catalog) or bare filenames (for
# uploads), so we resolve against several roots. Unresolved images are dropped and
# the page falls back to its corporate placeholder.
LIBRARY_ROOT = os.environ.get('BOV_LIBRARY_ROOT', ASSETS)
RESOLVE_ROOTS = [ROOT, ASSETS, LIBRARY_ROOT]

# Keys whose string values name an image file the assembler will try to read.
IMAGE_KEYS = {'photo', 'headshot', 'texture', 'divider_texture'}

app = FastAPI(title='TAG BOV build server')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],        # local dev: the console runs from file:// or localhost
    allow_methods=['*'],
    allow_headers=['*'],
)


def _resolve_image(value):
    """Return an absolute path to `value` if it exists, else None.

    Tries the path as given, then under each resolve root (by full relative path
    and by bare basename), so both catalog repo-relative paths and bare upload
    filenames resolve.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    candidates = [value]
    for r in RESOLVE_ROOTS:
        candidates.append(os.path.join(r, value))
        candidates.append(os.path.join(r, os.path.basename(value)))
    for p in candidates:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None


def sanitize(node):
    """Walk the config and resolve/prune image paths so a missing file never
    crashes the build. Resolvable paths are rewritten to absolute; unresolvable
    ones are removed, and (for stamp pages) so are the orphaned `boxes`."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            val = node[key]
            if key in IMAGE_KEYS and isinstance(val, str):
                resolved = _resolve_image(val)
                if resolved:
                    node[key] = resolved
                else:
                    del node[key]
                    if key == 'photo' and 'boxes' in node:
                        del node['boxes']  # nothing to stamp
            else:
                sanitize(val)
    elif isinstance(node, list):
        for item in node:
            sanitize(item)
    return node


@app.get('/api/health')
def health():
    return {
        'ok': True,
        'library': LIBRARY,
        'library_pages': (len(os.listdir(LIBRARY))
                          if os.path.isdir(LIBRARY) else 0),
        'library_root': LIBRARY_ROOT,
    }


@app.get('/')
def index():
    """Serve the console so it (and /assets, /api/*) share one origin."""
    return FileResponse(STUDIO)


@app.get('/api/assets')
def assets():
    """The preloaded asset catalog (run tools/build_asset_catalog.py to refresh)."""
    if os.path.isfile(CATALOG):
        with open(CATALOG, encoding='utf-8') as f:
            return json.load(f)
    return {'assets': []}


@app.get('/api/team')
def team():
    """The Anton Group roster: contacts, bios, headshot paths."""
    if os.path.isfile(TEAM):
        with open(TEAM, encoding='utf-8') as f:
            return json.load(f)
    return {'contacts': []}


# Serve committed imagery as thumbnails/sources for the console. Mounted last so
# the explicit routes above win; /assets/<folder>/<file> maps into assemble/assets.
app.mount('/assets', StaticFiles(directory=ASSETS), name='assets')


@app.post('/api/bov/build')
async def build(request: Request):
    config = await request.json()
    if not isinstance(config, dict) or 'order' not in config:
        return JSONResponse(
            status_code=400,
            content={'error': "config must be an object with an 'order' list"},
        )

    sanitize(config)

    out_path = tempfile.mktemp(suffix='.pdf')
    try:
        n, log = assembler.assemble(config, LIBRARY, out_path, FONTS, ASSETS)
        with open(out_path, 'rb') as f:
            pdf = f.read()
    except Exception as exc:  # surface the failure to the console, don't hang
        return JSONResponse(status_code=500,
                            content={'error': f'{type(exc).__name__}: {exc}'})
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)

    name = (config.get('meta', {}) or {}).get('property') or 'BOV'
    filename = ''.join(c for c in name if c.isalnum() or c in ' -_').strip() or 'BOV'
    return Response(
        content=pdf,
        media_type='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}.pdf"',
            'X-BOV-Pages': str(n),
            'X-BOV-Log': ' | '.join(log[-3:]),  # tail of the build log
        },
    )
