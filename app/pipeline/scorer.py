"""LLM-based intent scoring.

Takes a scraped post + a product description and asks a small model to
rate how good a sales lead it is on a 0-100 scale.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from app.config import settings

log = logging.getLogger(__name__)

SCORING_PROMPT = """You are a sales qualification analyst scoring a Reddit post as a lead for a specific product.

PRODUCT:
{product}

REDDIT POST:
Subreddit: {sub}
Title: {title}
Body: {body}

Score the post for how likely it is to convert to a customer. Think about:
- Is the author stating a problem the product solves?
- Are they actively evaluating / shopping for a solution? (Phrases like "looking for", "any recommendations", "alternative to", "stack", "we use X and")
- Have they shared budget, team size, or scale?
- Are they just venting, debating, or sharing their own project?

Return STRICT JSON only (no markdown fencing) matching:
{{"score": <0-100 int>, "reason": "<one short sentence>", "tags": ["<at most 3 short tags>"]}}

Where score is:
- 85-100: clear buying signal, asking for recommendations now, budget / stack / scale stated
- 65-84: active evaluation but soft, or problem clearly stated without ask
- 40-64: adjacent / problem mentioned in passing
- 0-39: not a lead (venting, promo, meta, off-topic)
"""


@dataclass
class ScoringResult:
    score: int
    reason: str
    tags: list[str]


class Scorer:
    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.scoring_model

    async def score(self, title: str, body: str, subreddit: str) -> ScoringResult:
        if not settings.anthropic_api_key:
            # Fallback for local testing without an API key.
            return ScoringResult(score=50, reason="(no LLM — placeholder score)", tags=[])

        prompt = SCORING_PROMPT.format(
            product=settings.product_description,
            sub=subreddit,
            title=title[:300],
            body=(body or "")[:1500],
        )
        try:
            msg = await self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(getattr(b, "text", "") for b in msg.content).strip()
            # Strip markdown fences if the model added them.
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            return ScoringResult(
                score=int(data.get("score", 0)),
                reason=str(data.get("reason", ""))[:300],
                tags=[str(t)[:40] for t in (data.get("tags") or [])][:3],
            )
        except Exception as e:
            log.warning("Scoring failed: %s", e)
            return ScoringResult(score=0, reason=f"scoring error: {e}", tags=[])
