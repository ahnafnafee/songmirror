"""Server-Sent Events — the live sync feed."""

import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


def _fmt(event) -> str:
    return f"data: {json.dumps(asdict(event))}\n\n"


@router.get("/events")
async def events(request: Request):
    bus = request.app.state.bus
    auth = request.app.state.profile_auth
    try:
        q = bus.subscribe()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def gen():
        try:
            yield ": connected\n\n"  # flush headers immediately
            for e in bus.recent():  # backfill the current/last pass
                if auth.enabled and not auth.signed_in(request):
                    return
                yield _fmt(e)
            # Poll disconnect each second so a closed browser is noticed promptly
            # (blocking on q.get for long would strand the generator).
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    event = None
                if auth.enabled and not auth.signed_in(request):
                    return
                yield _fmt(event) if event is not None else ": keep-alive\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")
