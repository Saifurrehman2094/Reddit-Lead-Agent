from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Draft, Lead
from app.pipeline.drafter import Drafter
from app.schemas import DraftOut

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


class DraftEdit(BaseModel):
    text: str


@router.post("/generate/{lead_id}", response_model=DraftOut)
async def generate_draft(lead_id: int, session: AsyncSession = Depends(get_session)):
    stmt = select(Lead).where(Lead.id == lead_id)
    res = await session.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")

    drafter = Drafter()
    result = await drafter.draft(lead.title, lead.body, lead.subreddit)

    draft = Draft(
        lead_id=lead.id,
        text=result.text,
        model=result.model,
        critic_notes=result.critic_notes,
    )
    session.add(draft)
    lead.status = "drafted"
    await session.commit()
    await session.refresh(draft)
    return draft


@router.put("/{draft_id}", response_model=DraftOut)
async def edit_draft(
    draft_id: int, body: DraftEdit, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(select(Draft).where(Draft.id == draft_id))
    draft = res.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    draft.text = body.text
    await session.commit()
    await session.refresh(draft)
    return draft
