from __future__ import annotations

from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Draft, Lead, ScanLog
from app.schemas import StatsOut

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
async def stats(session: AsyncSession = Depends(get_session)):
    start_of_day = datetime.combine(datetime.now(timezone.utc).date(), time.min)

    leads_today = (await session.execute(
        select(func.count(Lead.id)).where(Lead.fetched_at >= start_of_day)
    )).scalar() or 0

    drafts_today = (await session.execute(
        select(func.count(Draft.id)).where(Draft.created_at >= start_of_day)
    )).scalar() or 0

    approved_today = (await session.execute(
        select(func.count(Lead.id)).where(
            Lead.status.in_(["approved", "posted"]),
            Lead.fetched_at >= start_of_day,
        )
    )).scalar() or 0

    posts_scanned_today = (await session.execute(
        select(func.coalesce(func.sum(ScanLog.posts_scanned), 0)).where(
            ScanLog.started_at >= start_of_day
        )
    )).scalar() or 0

    last_scan = (await session.execute(
        select(ScanLog).order_by(ScanLog.started_at.desc()).limit(1)
    )).scalar_one_or_none()

    next_in = None
    if last_scan and last_scan.finished_at:
        delta = (datetime.now(timezone.utc) - last_scan.finished_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
        next_in = max(0, int(settings.scan_interval_minutes - delta))

    return StatsOut(
        leads_today=leads_today,
        drafts_today=drafts_today,
        approved_today=approved_today,
        posts_scanned_today=posts_scanned_today,
        last_scan_at=last_scan.started_at if last_scan else None,
        next_scan_in_minutes=next_in,
    )
