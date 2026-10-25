from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Niche
from app.schemas import NicheIn, NicheOut

router = APIRouter(prefix="/api/niches", tags=["niches"])


@router.get("", response_model=list[NicheOut])
async def list_niches(session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Niche).order_by(Niche.id))
    return res.scalars().all()


@router.post("", response_model=NicheOut)
async def create_niche(body: NicheIn, session: AsyncSession = Depends(get_session)):
    niche = Niche(**body.model_dump())
    session.add(niche)
    try:
        await session.commit()
    except Exception as e:
        raise HTTPException(400, f"Could not create niche: {e}")
    await session.refresh(niche)
    return niche


@router.put("/{niche_id}", response_model=NicheOut)
async def update_niche(
    niche_id: int, body: NicheIn, session: AsyncSession = Depends(get_session)
):
    res = await session.execute(select(Niche).where(Niche.id == niche_id))
    niche = res.scalar_one_or_none()
    if not niche:
        raise HTTPException(404, "Niche not found")
    for k, v in body.model_dump().items():
        setattr(niche, k, v)
    await session.commit()
    await session.refresh(niche)
    return niche


@router.delete("/{niche_id}")
async def delete_niche(niche_id: int, session: AsyncSession = Depends(get_session)):
    res = await session.execute(select(Niche).where(Niche.id == niche_id))
    niche = res.scalar_one_or_none()
    if not niche:
        raise HTTPException(404, "Niche not found")
    await session.delete(niche)
    await session.commit()
    return {"ok": True}
