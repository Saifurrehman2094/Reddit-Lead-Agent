# LeadRoom

A Reddit lead-generation MVP for **automation / AI agencies**. Watches
subreddits where business owners talk about manual work, broken CRMs and
pipelines gone dry; scores every new post for buying intent with an LLM;
drafts a helpful reply; and lets you approve it from a web dashboard.
Posting is manual copy-paste — on purpose, so you stay on the right side
of Reddit's rules for the MVP.

### What this seed targets

Four niches aimed at automation-agency buyers:

| Niche | Who it finds |
|---|---|
| **Automation pain** | Owners drowning in manual tasks, spreadsheets, VA work |
| **CRM optimization** | Teams with messy CRM data, broken pipelines, picking a CRM |
| **Lead gen seekers** | Founders / agencies looking for more clients, cold outreach help |
| **Agency ops** | Agency owners trying to scale, onboard faster, stop losing hours |

Across ~15 subreddits including r/Entrepreneur, r/smallbusiness, r/sales,
r/agency, r/HubSpot, r/CRM, r/nocode, r/Zapier, r/digital_marketing.

Edit `scripts/seed.py` and the `PRODUCT_DESCRIPTION` in `.env` to narrow
them to your exact offer.

## Stack

- **FastAPI** backend
- **SQLite** for storage (one `leadroom.db` file in the project root)
- **APScheduler** for the scan cron
- **Apify** (via its REST API) as the Reddit data source — no Reddit API key
  needed, no OAuth to set up
- **Anthropic Claude** for intent scoring and draft generation
- **Vanilla HTML/JS** dashboard served by FastAPI (no npm, no build step)

## Getting started (10 minutes)

### 1. Install

```bash
cd leadroom
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Python version:** 3.11, 3.12 or 3.13 is the safe choice. 3.14 works too
but only with the pinned `pydantic>=2.11.0` in requirements.txt — older
pydantic has no 3.14 wheels and pip will try to compile Rust from source.

If you hit a `pydantic-core` wheel-build error on Windows:
1. Easiest: install Python 3.13 and recreate the venv with `py -3.13 -m venv .venv`.
2. Alternative: stay on 3.14 and make sure `pip install -r requirements.txt`
   actually picks up `pydantic>=2.11.0` (run `pip show pydantic` to confirm).

### 2. Get API keys

**Apify** — https://console.apify.com/account/integrations
- Free tier includes $5 of platform credits per month, enough for roughly 2,000
  scraped posts.
- Copy the **Personal API token**.

**Anthropic** — https://console.anthropic.com/
- Any paid API key works. First-time users get a small credit.

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:
- Paste `APIFY_TOKEN` and `ANTHROPIC_API_KEY`.
- Set `PRODUCT_DESCRIPTION` to a short description of **your** product. This is
  fed to the LLM when scoring posts and drafting replies.
- Set `POSTING_HANDLE` to your Reddit username (used in the draft disclosure).

### 4. Seed example niches

```bash
python -m scripts.seed
```

This creates two example niches (SaaS tooling, Indie makers). Open the DB with
any SQLite GUI or edit `scripts/seed.py` to add your own.

### 5. Run

```bash
python -m app.main
```

Open http://localhost:8000.

On startup the scheduler fires immediately once, then every `SCAN_INTERVAL_MINUTES`
(default: 60). You can also hit the **Scan now** button in the dashboard, or:

```bash
curl -X POST http://localhost:8000/api/scan
```

The first scan takes 30-90 seconds (Apify spin-up) and will cost around
$0.01–0.03 in Apify credits plus a few cents in LLM calls.

## How it works

```
┌──────────────┐   every N min    ┌──────────────┐
│  Scheduler   ├─────────────────▶│   Scanner    │
└──────────────┘                  └──────┬───────┘
                                         │
                     ┌───────────────────┼───────────────────┐
                     ▼                   ▼                   ▼
             ┌──────────────┐   ┌──────────────┐    ┌──────────────┐
             │   Apify      │   │  Keyword     │    │   Scorer     │
             │   scraper    │──▶│  filter      │───▶│   (Haiku)    │
             └──────────────┘   └──────────────┘    └──────┬───────┘
                                                           │ score ≥ MIN_INTENT_SCORE
                                                           ▼
                                                   ┌──────────────┐
                                                   │  Postgres    │
                                                   │  / SQLite    │
                                                   └──────┬───────┘
                                                          │
         ┌────────────────────────────────────────────────┘
         ▼
┌──────────────┐    user clicks Generate     ┌──────────────┐
│  Dashboard   ├────────────────────────────▶│   Drafter    │
│              │                             │   (Sonnet)   │
│              │◀────────────────────────────┤  + Critic    │
└──────┬───────┘   draft + critic notes      └──────────────┘
       │ user approves
       ▼
   Copy to Reddit (manual, for MVP)
```

## Project layout

```
leadroom/
├─ app/
│  ├─ main.py              # FastAPI entry + scheduler
│  ├─ config.py            # env settings
│  ├─ db.py                # SQLAlchemy setup
│  ├─ models.py            # Niche, Lead, Draft, ScanLog
│  ├─ schemas.py           # Pydantic DTOs
│  ├─ scrapers/
│  │  ├─ base.py           # abstract RedditSource
│  │  └─ apify.py          # Apify adapter (swap to add Bright Data, etc.)
│  ├─ pipeline/
│  │  ├─ scanner.py        # the scan loop
│  │  ├─ scorer.py         # LLM intent scoring
│  │  └─ drafter.py        # LLM drafting + critic pass
│  └─ api/
│     ├─ leads.py          # /api/leads
│     ├─ niches.py         # /api/niches
│     ├─ drafts.py         # /api/drafts
│     ├─ stats.py          # /api/stats
│     └─ scan.py           # /api/scan
├─ static/
│  └─ index.html           # dashboard
├─ scripts/
│  └─ seed.py              # seed example niches
├─ requirements.txt
├─ .env.example
└─ README.md
```

## API reference

| Method | Path | What it does |
|---|---|---|
| GET  | `/api/leads` | List leads (query: `niche_id`, `status`, `min_score`, `limit`) |
| GET  | `/api/leads/{id}` | One lead with its drafts |
| POST | `/api/leads/{id}/status/{new_status}` | Set status: new, scored, drafted, approved, posted, rejected |
| GET  | `/api/niches` | List niches |
| POST | `/api/niches` | Create a niche |
| PUT  | `/api/niches/{id}` | Update a niche |
| DELETE | `/api/niches/{id}` | Delete a niche |
| POST | `/api/drafts/generate/{lead_id}` | Generate a draft reply with Claude |
| PUT  | `/api/drafts/{id}` | Save an edited draft |
| GET  | `/api/stats` | Daily counters |
| POST | `/api/scan` | Trigger a scan now (background) |

OpenAPI docs: http://localhost:8000/docs

## Costs (at MVP scale)

| Item | Monthly |
|---|---|
| Apify free tier ($5 credit) | $0 |
| Anthropic (Haiku scoring + Sonnet drafting) | ~$3 |
| Hosting (Railway / local) | $0–5 |
| **Total** | **≈ $3–8** |

If you overrun Apify's free credit, their Starter plan ($49/mo) covers roughly
20,000 scraped posts.

## Switching data providers

Everything behind `app/scrapers/base.RedditSource` is swappable:

```python
# app/scrapers/brightdata.py
class BrightDataRedditSource(RedditSource):
    async def fetch_new(self, subreddits, max_items=50):
        ...
```

Then change the one `ApifyRedditSource()` in `app/pipeline/scanner.py`.

## About the "3 accounts engaging with each other" idea

Deliberately left out. Reddit's Responsible Builder Policy bans using multiple
accounts for the same purpose, and automatic cross-engagement is the exact
pattern Reddit's AI detection targets. In the US it also falls under the FTC's
2024 fake-reviews rule, with civil penalties. This MVP uses one disclosed
account per user — your account.

## Reality checks before you post

- Follow each subreddit's self-promo rules. Many require 90% non-promo posts.
- The disclosure line is non-negotiable — leave it in every draft.
- If a subreddit has karma or account-age minimums, your reply will be removed
  silently. Build karma on your account first.

## Troubleshooting

**"Scan done: posts_scanned=0"** — The Apify actor didn't return items. Check
your Apify dashboard for the run log. Common causes: invalid subreddit names,
free tier exhausted, actor's version changed its field names (edit
`app/scrapers/apify.py`).

**All scores are 0** — `ANTHROPIC_API_KEY` is missing or invalid, or the
scoring model name is wrong. Check `app/config.py` defaults.

**Leads never appear** — `MIN_INTENT_SCORE` is too high, or your `keywords`
in the niche are too narrow. Try removing keywords (empty list = no prefilter)
and lowering the threshold temporarily to see what the scorer is giving you.

## Next steps when it's useful

1. Add Postgres (switch `DATABASE_URL`) when SQLite starts locking under load.
2. Add Reddit OAuth and a one-tap "post as me" button once posting is manual
   enough to irritate you.
3. Add pgvector + semantic similarity for better prefiltering.
4. Add multi-user auth (Supabase works well).
5. Add a Slack/Telegram notifier so new leads reach you in seconds instead of
   when you remember to open the dashboard.
