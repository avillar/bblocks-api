from __future__ import annotations

import os
from typing import Annotated, Sequence

import requests
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from starlette.responses import RedirectResponse

REGISTER_BASE_URL = os.environ.get('BBLOCKS_REGISTER_BASE_URL', 'https://opengeospatial.github.io/bblocks/')
if REGISTER_BASE_URL[-1] != '/':
    REGISTER_BASE_URL += '/'
CATALOG_URL = REGISTER_BASE_URL + 'register.json'
DEFAULT_MEDIATYPE = 'text/html'

bblocks = {}
bblock_ids = None


def bblock_id_to_path(bblock_id: str) -> str:
    return '/'.join(bblock_id.split('.')[1:])


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load BBlocks
    r = requests.get(CATALOG_URL)
    r.raise_for_status()
    global bblocks, bblock_ids
    bblocks = {bb['itemIdentifier']: bb for bb in r.json()}
    bblock_ids = list(sorted(bblocks.keys()))
    yield


app = FastAPI(lifespan=lifespan)


@app.get('/list')
async def bblock_list():
    return bblock_ids


@app.get('/bb/{bblock_id}')
async def view_bblock(bblock_id,
                      _mediatype: str = None,
                      _mediatype_header: Annotated[str | None, Header()] = None):
    bblock = bblocks.get(bblock_id)
    if not bblock:
        raise HTTPException(status_code=404, detail='Building block id not found')

    if not _mediatype:
        _mediatype = _mediatype_header
    if not _mediatype:
        _mediatype = DEFAULT_MEDIATYPE

    bblock_path = bblock_id_to_path(bblock_id)

    if _mediatype == 'text/html':
        return RedirectResponse(f"{REGISTER_BASE_URL}generateddocs/slate-build/{bblock_path}/")
    elif _mediatype == 'text/markdown':
        return RedirectResponse(f"{REGISTER_BASE_URL}generateddocs/markdown/{bblock_path}/index.md")
    elif _mediatype.startswith('application/schema+'):
        subtype = _mediatype[len('application/schema+'):]
        schema = None
        available_schemas = bblock.get('schema')
        if isinstance(available_schemas, str) and available_schemas.endswith('.' + subtype):
            schema = available_schemas
        elif isinstance(available_schemas, Sequence):
            schema = next((s for s in available_schemas if s.endswith('.' + subtype)), None)
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