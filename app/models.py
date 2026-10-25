from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Niche(Base):
    __tablename__ = "niches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    subreddits: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    leads: Mapped[list["Lead"]] = relationship(back_populates="niche", cascade="all, delete")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("post_id", name="uq_leads_post_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[str] = mapped_column(String(32), index=True)
    niche_id: Mapped[int] = mapped_column(ForeignKey("niches.id"))
    subreddit: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(80), default="")
    author_karma: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str] = mapped_column(String(500))
    posted_at: Mapped[datetime] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    intent_score: Mapped[int] = mapped_column(Integer, default=0)
    intent_reason: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)

    # new | scored | drafted | approved | posted | rejected
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)

    niche: Mapped["Niche"] = relationship(back_populates="leads")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="lead", cascade="all, delete")


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(80))
    critic_notes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    lead: Mapped["Lead"] = relationship(back_populates="drafts")


class ScanLog(Base):
    __tablename__ = "scan_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    posts_scanned: Mapped[int] = mapped_column(Integer, default=0)
    leads_created: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
