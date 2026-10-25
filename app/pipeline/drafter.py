"""LLM-based reply drafting with a critic pass."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from app.config import settings

log = logging.getLogger(__name__)

WRITER_PROMPT = """You are drafting a reply to a Reddit post as the founder of a product.
The goal is to be genuinely helpful first, product-relevant second.

PRODUCT:
{product}

POSTING AS: u/{handle} — a disclosed founder, not pretending to be a regular user.

REDDIT POST:
Subreddit: {sub}
Title: {title}
Body: {body}

RULES:
- Be helpful to this specific person. Mention the product only if it's the right answer.
- Honest disclosure: say in one short line that you're the founder of your product.
- No marketing voice. Write like a human on Reddit: lowercase-ish, short paragraphs, concrete.
- Never fabricate experiences, customers, revenue, or facts. If uncertain, say "I think" or "in my experience".
- Mention 1-2 alternatives (not just your product) when giving a recommendation.
- 60-180 words. No signature.
- Do not use em-dashes (—).

Return ONLY the reply text, no preamble."""

CRITIC_PROMPT = """You are a reviewer checking a Reddit reply drafted by an AI.

ORIGINAL POST:
{post}

DRAFT REPLY:
{draft}

Check for problems and return STRICT JSON (no markdown):
{{
  "fabrication": {{"ok": <true|false>, "note": "<short>"}},
  "disclosure": {{"ok": <true|false>, "note": "<short>"}},
  "tone": {{"ok": <true|false>, "note": "<short>"}},
  "promo_balance": {{"ok": <true|false>, "note": "<short>"}}
}}

Where:
- fabrication: the draft invents no numbers, customers, timeline, revenue, or specific experience the writer could not verify
- disclosure: the draft discloses the writer is the founder of their product (if the product is mentioned)
- tone: sounds like a human on Reddit, not marketing copy; not AI-cliched
- promo_balance: more helpful than pitchy; mentions at least one alternative where recommending something
"""


@dataclass
class DraftResult:
    text: str
    model: str
    critic_notes: list[dict]


class Drafter:
    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.drafting_model

    async def draft(self, title: str, body: str, subreddit: str) -> DraftResult:
        if not settings.anthropic_api_key:
            placeholder = (
                "(no ANTHROPIC_API_KEY set — this is a placeholder draft)\n\n"
                "Hey, saw your post. I'd probably look at a couple of options here..."
            )
            return DraftResult(text=placeholder, model="placeholder", critic_notes=[])

        prompt = WRITER_PROMPT.format(
            product=settings.product_description,
            handle=settings.posting_handle,
            sub=subreddit,
            title=title[:300],
            body=(body or "")[:1500],
        )
        try:
            msg = await self.client.messages.create(
                model=self.model,
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(getattr(b, "text", "") for b in msg.content).strip()
        except Exception as e:
            log.warning("Drafting failed: %s", e)
            return DraftResult(text=f"(drafting error: {e})", model=self.model, critic_notes=[])

        notes = await self._critique(title, body, text)
        return DraftResult(text=text, model=self.model, critic_notes=notes)

    async def _critique(self, title: str, body: str, draft: str) -> list[dict]:
        if not settings.anthropic_api_key:
            return []
        prompt = CRITIC_PROMPT.format(
            post=f"{title}\n\n{body[:800]}",
            draft=draft,
        )
        try:
            msg = await self.client.messages.create(
                model=settings.scoring_model,  # cheap model for critic
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            return [
                {"key": k, "ok": bool(v.get("ok")), "note": v.get("note", "")}
                for k, v in data.items()
                if isinstance(v, dict)
            ]
        except Exception as e:
            log.warning("Critic failed: %s", e)
            return []
