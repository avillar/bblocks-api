from __future__ import annotations

import os
from typing import Annotated, Sequence

import requests
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from accept_types import get_best_match

REGISTER_BASE_URL = os.environ.get('BBLOCKS_REGISTER_BASE_URL', 'https://opengeospatial.github.io/bblocks/')
if REGISTER_BASE_URL[-1] != '/':
    REGISTER_BASE_URL += '/'
CATALOG_URL = REGISTER_BASE_URL + 'register.json'
DEFAULT_MEDIATYPE = 'text/html'
ROOT_PATH = os.environ.get('BBLOCKS_ROOT_PATH', '')
ACCEPTED_MEDIATYPES = [
    'text/html',
    'text/markdown',
    'application/ld+json',
    'application/schema+json',
    'application/schema+yaml',
    'application/json',
]
SCHEMA_MEDIATYPES = {
    'application/schema+json': 'application/json',
    'application/schema+yaml': 'application/yaml',
}
DOC_MEDIATYPES = {
    'text/html': 'slate',
    'text/markdown': 'markdown',
    'application/json': 'json-full',
}

bblocks = {}
bblock_ids = None

scheduler = AsyncIOScheduler()


def bblock_id_to_path(bblock_id: str) -> str:
    return '/'.join(bblock_id.split('.')[1:])


@scheduler.scheduled_job('interval', hours=1)
async def update_building_blocks():
    print('Updating building blocks')
    r = requests.get(CATALOG_URL)
    r.raise_for_status()
    global bblocks, bblock_ids
    bblocks = {bb['itemIdentifier']: bb for bb in r.json()}
    bblock_ids = list(sorted(bblocks.keys()))
    print(f"Found {len(bblock_ids)} building blocks")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await update_building_blocks()
    scheduler.start()
    yield


app = FastAPI(lifespan=lifespan, root_path=ROOT_PATH)

@app.get('/')
async def index():
    return {
        'name': 'bblocks-api',
        'accepted-mediatypes': ACCEPTED_MEDIATYPES
    }


@app.get('/list')
async def bblock_list():
    return bblock_ids


@app.get('/bb/{bblock_id}')
async def view_bblock(bblock_id,
                      _mediatype: str = None,
                      accept: Annotated[str | None, Header()] = None):
    bblock = bblocks.get(bblock_id)
    import json
    print(json.dumps(bblock, indent=2))
    if not bblock:
        raise HTTPException(status_code=404, detail='Building block id not found')

    if not _mediatype and not accept:
        _mediatype = DEFAULT_MEDIATYPE
    elif _mediatype:
        if _mediatype not in ACCEPTED_MEDIATYPES:
            raise HTTPException(status_code=400, detail='Unsupported media type')
    elif accept:
        _mediatype = get_best_match(accept, available_types=ACCEPTED_MEDIATYPES)
        if not _mediatype:
            raise HTTPException(status_code=400, detail='Unsupported media type')

    bblock_path = bblock_id_to_path(bblock_id)

    if _mediatype in DOC_MEDIATYPES:
        url = bblock.get('documentation', {}).get(DOC_MEDIATYPES[_mediatype], {}).get('url')
        if url:
            return RedirectResponse(url)
        else:
            raise HTTPException(status_code=404, detail=f'Documentation for type {_mediatype} not found')

    elif _mediatype.startswith('application/schema+'):
        subtype = SCHEMA_MEDIATYPES.get(_mediatype)
        schema = bblock.get('schema', {}).get(subtype)
        if schema:
            return RedirectResponse(schema)
        else:
            raise HTTPException(status_code=404, detail=f'Schema for type {subtype} not found')

    elif _mediatype == 'application/ld+json':
        ld_context = bblock.get('ldContext')
        if ld_context:
            return RedirectResponse(ld_context)
        else:
            raise HTTPException(status_code=404, detail='No JSON-LD context found for the building block')

    raise HTTPException(status_code=400, detail='Unsupported media type')