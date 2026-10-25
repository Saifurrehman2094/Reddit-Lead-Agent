"""Seed the DB with niches tuned for an automation / AI agency selling:
   - daily task automation (Zapier/Make/n8n builds, custom scripts)
   - CRM setup, cleanup and optimization (HubSpot, Pipedrive, GHL, Salesforce)
   - lead generation services

Run from the project root:  python -m scripts.seed
Edit the niches below if your offer is narrower."""
import asyncio

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import Niche

SEED_NICHES = [
    {
        "name": "Automation pain",
        "description": "Business owners drowning in manual work — repetitive tasks, "
                       "copy-paste jobs, spreadsheet workflows that are breaking.",
        "keywords": [
            "automate", "automation", "manual", "repetitive", "tedious",
            "spreadsheet", "google sheet", "excel", "copy paste", "copy-paste",
            "zapier", "make.com", "n8n", "workflow", "integrate", "sync",
            "connect", "no-code", "nocode", "virtual assistant", "VA",
            "drowning", "overwhelmed", "too many tools", "wasting time",
        ],
        "subreddits": [
            "Entrepreneur", "smallbusiness", "EntrepreneurRideAlong",
            "nocode", "automation", "Zapier", "sweatystartup",
        ],
    },
]


async def main():
    await init_db()
    async with SessionLocal() as session:
        for n in SEED_NICHES:
            exists = await session.execute(
                select(Niche).where(Niche.name == n["name"])
            )
            if exists.scalar_one_or_none():
                print(f"[skip] {n['name']} already exists")
                continue
            session.add(Niche(**n))
            print(f"[+] {n['name']}  ({len(n['subreddits'])} subs, {len(n['keywords'])} keywords)")
        await session.commit()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
