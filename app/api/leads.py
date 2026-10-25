from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Lead
from app.schemas import LeadOut

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("", response_model=list[LeadOut])
async def list_leads(
    session: AsyncSession = Depends(get_session),
    niche_id: int | None = None,
    status: str | None = None,
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = select(Lead).options(selectinload(Lead.drafts)).order_by(desc(Lead.posted_at))
    if niche_id is not None:
        stmt = stmt.where(Lead.niche_id == niche_id)
    if status:
        stmt = stmt.where(Lead.status == status)
    if min_score:
        stmt = stmt.where(Lead.intent_score >= min_score)
    stmt = stmt.limit(limit)
    res = await session.execute(stmt)
    return res.scalars().all()


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: int, session: AsyncSession = Depends(get_session)):
    stmt = select(Lead).options(selectinload(Lead.drafts)).where(Lead.id == lead_id)
    res = await session.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


@router.post("/{lead_id}/status/{new_status}", response_model=LeadOut)
async def update_status(
    lead_id: int, new_status: str, session: AsyncSession = Depends(get_session)
):
    if new_status not in {"new", "scored", "drafted", "approved", "posted", "rejected"}:
        raise HTTPException(400, "Invalid status")
    stmt = select(Lead).options(selectinload(Lead.drafts)).where(Lead.id == lead_id)
    res = await session.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.status = new_status
    await session.commit()
    await session.refresh(lead)
    return lead
