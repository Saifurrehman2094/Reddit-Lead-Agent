from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks

from app.pipeline.scanner import run_scan

router = APIRouter(prefix="/api/scan", tags=["scan"])

_scan_lock = asyncio.Lock()


async def _run_locked():
    if _scan_lock.locked():
        return
    async with _scan_lock:
        await run_scan()


@router.post("")
async def trigger_scan(background: BackgroundTasks):
    """Fire a scan in the background. Returns immediately."""
    background.add_task(_run_locked)
    return {"ok": True, "message": "Scan started in background"}
