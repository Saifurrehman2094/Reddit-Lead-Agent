"""Apify Reddit scraper adapter.

Uses the Apify REST API in ASYNC mode:
  1. Start the run      → POST /v2/acts/{actor}/runs
  2. Poll until finished → GET  /v2/actor-runs/{run_id}
  3. Fetch dataset      → GET  /v2/datasets/{dataset_id}/items

This replaces run-sync-get-dataset-items, which had a 5 min hard cap on
Apify's side and often hit our client HTTP timeout before completing.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.scrapers.base import RedditSource, ScrapedPost

log = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"

# A single scrape can run up to this many seconds before we give up.
MAX_RUN_SECONDS = 600  # 10 minutes
# How often we poll Apify for run status.
POLL_INTERVAL = 5
# Statuses that mean the run has finished (one way or another).
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "TIMING-OUT"}


def _parse_dt(v: Any) -> datetime:
    if v is None:
        return datetime.now(timezone.utc)
    if isinstance(v, (int, float)):
        if v > 1e12:
            v = v / 1000
        return datetime.fromtimestamp(v, tz=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            pass
    return datetime.now(timezone.utc)


class ApifyRedditSource(RedditSource):
    def __init__(self, token: str | None = None, actor_id: str | None = None) -> None:
        self.token = token or settings.apify_token
        self.actor_id = actor_id or settings.apify_actor_id

    async def fetch_new(
        self, subreddits: list[str], max_items: int = 30
    ) -> list[ScrapedPost]:
        if not self.token:
            raise RuntimeError("APIFY_TOKEN is not set — add it to .env")
        if not subreddits:
            return []

        payload = {
            "startUrls": [
                {"url": f"https://www.reddit.com/r/{s.lstrip('r/').strip()}/new/"}
                for s in subreddits
            ],
            "maxItems": max_items,
            "maxPostCount": max_items,
            "maxComments": 0,
            "maxCommunitiesCount": len(subreddits),
            "scrollTimeout": 40,
            "proxy": {"useApifyProxy": True},
            "searchPosts": True,
            "searchComments": False,
            "searchCommunities": False,
            "searchUsers": False,
        }

        # Timeouts for individual HTTP calls (not the overall scrape).
        timeout = httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            # 1. Start the run.
            start_url = f"{APIFY_BASE}/acts/{self.actor_id}/runs"
            log.info("Apify: starting run on %s with %d subs", self.actor_id, len(subreddits))
            resp = await client.post(
                start_url, params={"token": self.token}, json=payload
            )
            resp.raise_for_status()
            run_data = resp.json().get("data", {})
            run_id = run_data.get("id")
            dataset_id = run_data.get("defaultDatasetId")
            if not run_id or not dataset_id:
                raise RuntimeError(f"Apify did not return a run id: {run_data}")
            log.info("Apify: run %s started (dataset %s)", run_id, dataset_id)

            # 2. Poll until finished.
            status = run_data.get("status", "RUNNING")
            elapsed = 0
            while status not in TERMINAL_STATUSES:
                if elapsed >= MAX_RUN_SECONDS:
                    log.warning(
                        "Apify run %s exceeded %ds, abandoning (it will keep running on Apify)",
                        run_id, MAX_RUN_SECONDS,
                    )
                    break
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                status_resp = await client.get(
                    f"{APIFY_BASE}/actor-runs/{run_id}", params={"token": self.token}
                )
                if status_resp.status_code != 200:
                    log.warning("Apify status poll returned %d, continuing", status_resp.status_code)
                    continue
                data = status_resp.json().get("data", {})
                status = data.get("status", status)
                if elapsed % 30 == 0:
                    log.info("Apify run %s: %s (%ds elapsed)", run_id, status, elapsed)

            log.info("Apify run %s finished with status %s after %ds", run_id, status, elapsed)

            # 3. Fetch dataset items (works even for partial / failed runs).
            items_resp = await client.get(
                f"{APIFY_BASE}/datasets/{dataset_id}/items",
                params={"token": self.token, "format": "json", "clean": "true"},
            )
            items_resp.raise_for_status()
            items = items_resp.json()

        posts = [self._normalize(it) for it in items if self._is_post(it)]
        log.info("Apify: dataset returned %d items, %d parsed as posts", len(items), len(posts))
        return posts

    def _is_post(self, it: dict) -> bool:
        dt = (it.get("dataType") or "").lower()
        if dt and dt not in ("post", "posts", "redditpost"):
            return False
        return bool(it.get("id") or it.get("postId") or it.get("parsedId"))

    def _normalize(self, it: dict) -> ScrapedPost:
        post_id = str(it.get("id") or it.get("postId") or it.get("parsedId") or "")
        sub = (
            it.get("parsedCommunityName")
            or it.get("communityName")
            or it.get("subreddit")
            or ""
        )
        if sub and not sub.startswith("r/"):
            sub = f"r/{sub}"
        author = it.get("username") or it.get("author") or ""
        return ScrapedPost(
            post_id=post_id,
            subreddit=sub,
            title=(it.get("title") or "").strip(),
            body=(it.get("body") or it.get("text") or it.get("selftext") or "").strip(),
            author=author,
            author_karma=int(it.get("userKarma") or it.get("karma") or 0),
            score=int(it.get("upVotes") or it.get("score") or it.get("ups") or 0),
            num_comments=int(it.get("numberOfComments") or it.get("numComments") or 0),
            url=it.get("url") or f"https://reddit.com/comments/{post_id}",
            posted_at=_parse_dt(it.get("createdAt") or it.get("created") or it.get("created_utc")),
        )