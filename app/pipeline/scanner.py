"""The main scan loop: fetch new Reddit posts, keyword-prefilter, LLM-score, store."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Lead, Niche, ScanLog
from app.pipeline.scorer import Scorer
from app.scrapers.apify import ApifyRedditSource

log = logging.getLogger(__name__)


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    t = text.lower()
    return any(k.lower() in t for k in keywords)


async def run_scan() -> dict:
    """Run one scan cycle for every niche. Returns a summary dict."""
    source = ApifyRedditSource()
    scorer = Scorer()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.max_post_age_hours)

    summary = {"posts_scanned": 0, "leads_created": 0, "niches": 0, "errors": []}

    async with SessionLocal() as session:
        scan_log = ScanLog()
        session.add(scan_log)
        await session.commit()
        await session.refresh(scan_log)

        res = await session.execute(select(Niche))
        niches = res.scalars().all()

    for niche in niches:
        summary["niches"] += 1
        subs = niche.subreddits or []
        if not subs:
            continue
        try:
            posts = await source.fetch_new(subs, max_items=30)
        except Exception as e:
            log.exception("Scrape failed for niche %s: %s", niche.name, e)
            summary["errors"].append(f"{niche.name}: {e}")
            continue

        summary["posts_scanned"] += len(posts)
        log.info("Niche %s: %d posts fetched", niche.name, len(posts))

        for post in posts:
            posted_at = post.posted_at
            # Normalise to tz-aware UTC
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=timezone.utc)
            if posted_at < cutoff:
                continue
            if not _matches_keywords(f"{post.title}\n{post.body}", niche.keywords or []):
                continue

            async with SessionLocal() as session:
                existing = await session.execute(
                    select(Lead).where(Lead.post_id == post.post_id)
                )
                if existing.scalar_one_or_none():
                    continue

                result = await scorer.score(post.title, post.body, post.subreddit)
                if result.score < settings.min_intent_score:
                    log.info("Skipping low-score post %s (%d): %s",
                             post.post_id, result.score, post.title[:60])
                    continue

                lead = Lead(
                    post_id=post.post_id,
                    niche_id=niche.id,
                    subreddit=post.subreddit,
                    title=post.title,
                    body=post.body,
                    author=post.author,
                    author_karma=post.author_karma,
                    score=post.score,
                    num_comments=post.num_comments,
                    url=post.url,
                    posted_at=posted_at.replace(tzinfo=None),
                    intent_score=result.score,
                    intent_reason=result.reason,
                    tags=result.tags,
                    status="scored",
                )
                session.add(lead)
                await session.commit()
                summary["leads_created"] += 1
                log.info("Lead %d/%s score=%d: %s",
                         lead.id or 0, post.post_id, result.score, post.title[:60])

            # Gentle pacing so we don't hammer the LLM.
            await asyncio.sleep(0.3)

    async with SessionLocal() as session:
        res = await session.execute(select(ScanLog).where(ScanLog.id == scan_log.id))
        sl = res.scalar_one()
        sl.finished_at = datetime.now(timezone.utc)
        sl.posts_scanned = summary["posts_scanned"]
        sl.leads_created = summary["leads_created"]
        sl.error = "; ".join(summary["errors"])[:1000]
        await session.commit()

    log.info("Scan done: %s", summary)
    return summary
