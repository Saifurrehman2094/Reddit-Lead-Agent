from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NicheIn(BaseModel):
    name: str
    description: str = ""
    keywords: list[str] = []
    subreddits: list[str] = []


class NicheOut(NicheIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str
    model: str
    critic_notes: list
    created_at: datetime


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: str
    niche_id: int
    subreddit: str
    title: str
    body: str
    author: str
    author_karma: int
    score: int
    num_comments: int
    url: str
    posted_at: datetime
    fetched_at: datetime
    intent_score: int
    intent_reason: str
    tags: list
    status: str
    drafts: list[DraftOut] = []


class StatsOut(BaseModel):
    leads_today: int
    drafts_today: int
    approved_today: int
    posts_scanned_today: int
    last_scan_at: Optional[datetime] = None
    next_scan_in_minutes: Optional[int] = None
