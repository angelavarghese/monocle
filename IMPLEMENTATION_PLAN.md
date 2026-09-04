# Smart Market Watchlist — Implementation Plan

**Event:** Code by Groww (HackerEarth) · 72-hour build
**Stack:** Next.js + TS + Tailwind + shadcn/ui · FastAPI · PostgreSQL · SQLAlchemy · Pydantic · JWT

---

## 1. Product framing — the decisions the PS leaves open

The PS deliberately doesn't tell you what "meaningful" means. Judges will be evaluating the *thinking*, not just working CRUD. Here's the stance this plan takes — adjust before you start building, don't just accept it blindly.

### 1.1 What counts as a "meaningful change"
Not every price tick matters. Define a **change engine** that flags a symbol only when one of these fires, since the user's **last visit** (not since app start):

**Confirmed formula:**
```
Meaningfulness = unusual price movement
               + unusual volume
               + company-specific event
               + deviation from market/sector
               + importance to the user's interests
```

| Signal | Trigger | Data source | Why it matters |
|---|---|---|---|
| Price move | \|% change\| ≥ threshold (e.g. 2% intraday, configurable) | Finnhub quote | Filters noise from signal |
| Range breakout | New 30-day high/low crossed | Computed from stored `price_snapshots` | Structural, not just noisy |
| Volume spike | Volume ≥ 2× the 20-day average | Finnhub quote | Often precedes/accompanies real news |
| Company event | Relevant headline in last N hours | Finnhub company-news | Explains *why*, not just *that* |
| Sector deviation | `symbol_change − sector_avg_change` beyond threshold | Finnhub company-profile (industry) + peer snapshots you're already polling | "Fell more than the sector" is more informative than "fell" |
| User interest | Item explicitly marked high-priority, or high view frequency | `watchlist_items.is_priority` flag | Same move matters more on a stock the user actually cares about |
| Staleness | Last known price older than N minutes | `price_snapshots.fetched_at` | Tells the user *not* to trust the number blindly |

Each watchlist item gets a computed `change_status`: `quiet | notable | significant | stale`, a **confidence level** (`High | Medium | Low`, based on how many signals fired together and whether a corroborating news event exists), and a one-line human-readable reason ("Unusual volume + major partnership announcement" / "Fell significantly more than the EV sector"). This reason string plus confidence is the actual product differentiator — surface both prominently, don't bury them in a tooltip.

**Confidence scoring, kept simple:** count how many of the five signals fired for that item. 1 signal → Low, 2 → Medium, 3+ or (any signal + confirming news headline) → High. This gives you the 🔴/🟠/🟡 tiering directly — significant+High confidence = 🔴, significant+Medium or notable+High = 🟠, notable+Low = 🟡, quiet = goes in the "Nothing meaningful changed" list.

**Worked example (matches the home-page mock):**
- NVIDIA: price move ✓ + volume spike ✓ + company event ✓ → 3 signals → High confidence → 🔴
- TESLA: price move ✓ + sector deviation ✓ (fell more than EV sector) + upcoming-earnings context → 🟠
- AMD: price move ✓ + company event ✓ (analyst upgrade) but no volume/sector confirmation → 🟡
- AAPL/MSFT/AMZN/GOOGL: no signals fired → grouped under "Nothing meaningful changed", flat list, no cards

### 1.2 What information to surface
- Per item: symbol, name, current price, delta since last visit (not since yesterday's close — this is the key twist), % change, volume vs average, a small sparkline, and the change reason.
- A **"Since you last checked"** header per watchlist showing last-visit timestamp and a summary count ("3 notable, 1 significant, 1 stale").
- Sorting: significant-first by default, not alphabetical. This alone makes it feel "smart."

### 1.3 How state persists across sessions/devices
- Real user accounts (JWT), not localStorage-only. `last_viewed_at` is stored server-side **per watchlist**, updated only when the user explicitly opens/refreshes that watchlist's detail view (not on every API poll) — so "since last checked" is meaningful and multi-device consistent.
- Also store a `previous_snapshot_id` reference per watchlist item at the moment of last view, so the diff is against exactly what the user last saw, not a rolling window.

### 1.4 Handling stale / delayed / conflicting data
- Every price fetch is stored as an immutable `price_snapshot` row (symbol, price, volume, source, fetched_at). Never overwrite — append.
- The API always returns the **latest snapshot** plus its `fetched_at` age. Frontend renders a staleness badge if age > threshold (e.g. 5 min for a free-tier API).
- If two snapshots conflict (fast repeated polling returns odd data, e.g. price outside a sane band from previous snapshot), don't silently trust it — mark `flagged_conflict = true` and prefer the previous good value until confirmed by a second fetch.
- Background refresh is scoped to **symbols actually on some user's watchlist** — no wasted calls on untracked tickers.

### 1.5 Scaling for larger watchlists / more users
- Dedupe fetches: if 500 users all watch AAPL, fetch it once per polling cycle, not 500 times. Maintain a `tracked_symbols` table (symbol → ref count), poll that set on a schedule, and fan the snapshot out to all watchlists containing it.
- Pagination on watchlist items and on historical snapshots.
- Push the "what changed" computation to be done at read-time from stored snapshots (cheap query), not recomputed by a heavy job — keeps the background job doing only ingestion.
- Mention (don't necessarily build) Redis for a hot-price cache as the next scaling step, and horizontal scaling of the FastAPI app behind the same Postgres.

### 1.6 Where to keep it simple
- Single external market-data API (see below), synchronous polling loop (APScheduler in-process) rather than a distributed task queue — this is a 72-hour build, not production infra. Say so explicitly in your demo: "here's what I simplified and why, and here's what I'd do at scale."

---

## 2. External market data source

Pick **one** free-tier API and commit — don't burn hours evaluating options:
- **Finnhub** (recommended: generous free tier, simple REST, has quote + candle endpoints) — https://finnhub.io
- Alternative: Twelve Data or Alpha Vantage (lower free rate limits, more likely to throttle during a demo).

This plan assumes **Finnhub**. Swap freely — only the `market_data` service module needs to change.

### 2.1 News / company-events source
Use **Finnhub's company-news endpoint** — same provider, same API key, one less rate limit to track. Only fetch news for a symbol when it already shows a price or volume anomaly (don't poll news for every watchlist item on every cycle — wasteful and irrelevant most of the time). Store fetched headlines alongside the triggering snapshot so the "reason" string and the chat feature can both reference them without re-fetching.

If you want sentiment scoring out of the box instead of writing your own heuristic, Alpha Vantage's `NEWS_SENTIMENT` endpoint is the alternative — but it's a separate key with a much tighter free-tier rate limit, so only switch if the classification quality matters more to you than simplicity.

---

## 3. Backend architecture (FastAPI)

```
backend/
├── app/
│   ├── main.py                  # FastAPI app, CORS, router mounting
│   ├── core/
│   │   ├── config.py             # Settings via pydantic-settings, reads .env
│   │   ├── security.py           # JWT create/verify, password hashing
│   │   └── scheduler.py          # APScheduler setup for background polling
│   ├── db/
│   │   ├── base.py                # SQLAlchemy Base
│   │   ├── session.py             # engine + SessionLocal + get_db dependency
│   │   └── init_db.py             # create_all / first-run helper
│   ├── models/
│   │   ├── user.py
│   │   ├── watchlist.py           # Watchlist, WatchlistItem
│   │   ├── snapshot.py            # PriceSnapshot, TrackedSymbol
│   ├── schemas/
│   │   ├── user.py
│   │   ├── watchlist.py
│   │   ├── market.py
│   ├── crud/
│   │   ├── user.py
│   │   ├── watchlist.py
│   │   ├── snapshot.py
│   ├── services/
│   │   ├── market_data.py         # Finnhub client wrapper (quotes + company news)
│   │   ├── change_engine.py       # computes change_status, confidence, reason string
│   │   ├── polling.py             # background job: refresh tracked symbols
│   │   ├── llm_client.py          # Groq client wrapper
│   │   └── chat_guardrails.py     # pre-filter + output-side keyword check
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py            # /auth/register, /auth/login
│   │       ├── watchlists.py      # CRUD for watchlists + items
│   │       ├── market.py          # GET quote/history for a symbol
│   │       ├── chat.py            # POST /chat — grounded Q&A
│   │       └── deps.py            # get_current_user dependency
│   └── __init__.py
├── alembic/                       # migrations (optional but recommended)
├── requirements.txt
├── .env.example
└── README.md (backend-specific, or merged into root README)
```

### Key data model
- `users(id, email, hashed_password, created_at)`
- `watchlists(id, user_id, name, last_viewed_at, created_at)`
- `watchlist_items(id, watchlist_id, symbol, added_at, last_seen_snapshot_id, is_priority)`
- `tracked_symbols(symbol, sector, ref_count, last_polled_at)`
- `price_snapshots(id, symbol, price, volume, high_30d, low_30d, avg_volume_20d, fetched_at, flagged_conflict)`
- `news_headlines(id, symbol, headline, source, published_at, linked_snapshot_id)`

### Core endpoints
- `POST /auth/register`, `POST /auth/login` → JWT
- `GET /watchlists`, `POST /watchlists`, `DELETE /watchlists/{id}`
- `POST /watchlists/{id}/items` (add symbol), `DELETE /watchlists/{id}/items/{item_id}`, `PATCH .../items/{item_id}` (toggle `is_priority`)
- `GET /watchlists/{id}` → items + computed change_status/confidence/reason, and marks `last_viewed_at = now()` for that watchlist
- `GET /market/{symbol}/history` → for sparkline
- `POST /chat` → `{ question }` in, guardrailed + grounded answer out (see §5)

---

## 4. Frontend architecture (Next.js App Router)

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                   # redirect to /login or /dashboard
│   ├── login/page.tsx
│   ├── register/page.tsx
│   └── dashboard/
│       ├── page.tsx               # list of watchlists
│       └── [id]/page.tsx          # watchlist detail: items sorted by significance
├── components/
│   ├── ui/                        # shadcn/ui generated components
│   ├── watchlist/
│   │   ├── WatchlistCard.tsx
│   │   ├── ItemRow.tsx            # price, delta, change badge, reason string
│   │   ├── ChangeBadge.tsx        # quiet/notable/significant/stale styling
│   │   └── Sparkline.tsx
│   ├── chat/
│   │   └── ChatPanel.tsx          # minimal message list + input, scoped to watchlist Q&A
│   └── layout/Navbar.tsx
├── lib/
│   ├── api.ts                     # fetch wrapper, attaches JWT
│   ├── auth.ts                    # token storage/refresh helpers
│   └── types.ts
├── .env.local.example
├── package.json
└── tailwind.config.ts
```

Auth token: store JWT in an httpOnly-ish approach isn't possible from client fetch alone in App Router without a backend-for-frontend, so for hackathon scope: store in memory + `localStorage` fallback, clearly note in README this is a simplification (production would use httpOnly cookies set by a BFF).

---

## 5. AI Chat Assistant (Groq) — scope and guardrails

**Scope:** read-only Q&A grounded in the user's own watchlist data. Not general market chat, not investment advice. This narrow scope is what makes the guardrails below tractable within a hackathon timeline and a token budget.

### 5.1 Guardrail pipeline (in order — each stage can short-circuit before spending tokens)

1. **Pre-filter (no LLM call, no tokens spent)** — check the question against the symbols in the user's watchlist plus a small finance-term keyword list. If neither matches, return a hardcoded refusal immediately: *"I can only answer questions about the stocks on your watchlist."*
2. **Scoped context injection** — parse which symbol(s) the question references, pull only that item's latest snapshot, computed change reason, and last 2–3 stored headlines. Never inject the full watchlist or raw candle history — this is your main token-control lever.
3. **System prompt, scope-locked:**
   ```
   You are a market-data assistant restricted to the user's watchlist.
   Only answer questions about the specific stocks and data provided in
   context. Do not give investment advice, buy/sell recommendations, or
   price predictions. If asked about anything outside the provided data
   or general market mechanics, say you can't help with that.
   Keep responses under 3 sentences.
   ```
4. **Output-side check** — after the response returns, run a cheap keyword scan for advice-adjacent phrasing ("you should buy", "I recommend", explicit predictions). If matched, discard and return a canned fallback instead of showing it.
5. **Hardcoded disclaimer** — append "Not financial advice." from backend code on every response; never rely on the model to include it.
6. **Rate limiting** — cap chat requests per user (e.g. 10/min) so the free-tier Groq quota survives the judging window.

### 5.2 Model and token budget
- Model: `llama-3.1-8b-instant` on Groq — fast enough for chat UX, cheap enough that the token ceiling is rarely the binding constraint at this scale.
- Cap `max_tokens` on responses (150–200) to keep replies terse and on-brand with the dashboard's "one-line reason" style.
- Log every chat request's token usage during the build so you have real numbers if judges ask about cost/scaling.

### 5.3 New backend pieces this adds
```
backend/app/services/chat_guardrails.py   # pre-filter + output-side keyword check
backend/app/services/llm_client.py        # Groq client wrapper
backend/app/api/v1/chat.py                # POST /chat — takes a question, returns grounded answer
```
Frontend adds a simple chat panel (`components/chat/ChatPanel.tsx`) on the dashboard or watchlist detail view — keep it minimal, a scrollable message list + input, no need for streaming unless time allows.

---

## 6. .env files — generate these exactly, as samples (no real secrets committed)

### `backend/.env.example`
```
# --- Database ---
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smart_watchlist

# --- Auth ---
JWT_SECRET_KEY=replace-with-a-long-random-string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# --- Market data + news provider (same key covers both, Finnhub) ---
MARKET_DATA_PROVIDER=finnhub
FINNHUB_API_KEY=replace-with-your-finnhub-api-key

# --- AI chat assistant ---
GROQ_API_KEY=replace-with-your-groq-api-key
GROQ_MODEL=llama-3.1-8b-instant
CHAT_MAX_TOKENS=200
CHAT_RATE_LIMIT_PER_MINUTE=10

# --- CORS ---
CORS_ORIGINS=http://localhost:3000

# --- Polling ---
POLL_INTERVAL_SECONDS=60
STALE_THRESHOLD_MINUTES=5

# --- Change engine thresholds ---
PRICE_MOVE_THRESHOLD_PCT=2.0
VOLUME_SPIKE_MULTIPLIER=2.0
SECTOR_DEVIATION_THRESHOLD_PCT=2.0
```

### `frontend/.env.local.example`
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

Ask for this explicitly when you scaffold: **generate a real `.env.example` file at each of these paths with the placeholders above**, and load `backend/.env` via `pydantic-settings`/`python-dotenv` in `core/config.py`. Never commit the actual `.env`.

---

## 7. requirements.txt (backend)

```
fastapi
uvicorn[standard]
sqlalchemy
psycopg2-binary
pydantic
pydantic-settings
python-jose[cryptography]
passlib[bcrypt]
python-dotenv
apscheduler
httpx
alembic
groq
```

Pin versions once you scaffold (`pip freeze > requirements.txt` after first install) rather than hand-guessing numbers — keep the unpinned list above as the source of truth for what to install.

---

## 8. README.md — required sections

Ask for the README to include, in this order:
1. **Project overview** — one paragraph, plus the "meaningful change" philosophy from §1.1 (this is what you'll say in the demo).
2. **Tech stack table** (as given).
3. **Prerequisites** — Node version, Python version, PostgreSQL installed locally, a Finnhub API key (free signup link) for market data + news, and a Groq API key (free signup link) for the chat assistant.
4. **Setup — Database**: create a local Postgres DB named `smart_watchlist`, or `docker compose up -d db` if you choose the Compose route.
5. **Setup — Backend**: activate your own venv, `pip install -r requirements.txt`, copy `.env.example` → `.env` and fill in `FINNHUB_API_KEY`, run `alembic upgrade head` (or `init_db.py` if skipping migrations), then `uvicorn app.main:app --reload`.
6. **Setup — Frontend**: `npm install`, copy `.env.local.example` → `.env.local`, `npm run dev`.
7. **Running both together** — ports (backend :8000, frontend :3000), and a note that `/docs` (Swagger) is available on the backend for judges to poke at the API directly.
8. **Design decisions** — a condensed version of §1, so judges reading the repo (not just watching the demo) get the "why."
9. **What I'd do with more time** — scaling (Redis cache, task queue), multi-provider fallback for market data, websocket push instead of polling.

---

## 9. Build order (for the 72 hours)

1. **Hour 0–4**: Scaffold both repos, Postgres running, `.env` files in place, "hello world" endpoint reachable from frontend. Get Git + GitHub pushed early — a working skeleton commit on hour 1 is worth more than a perfect one on hour 60.
2. **Hour 4–10**: DB models + migrations, auth (register/login/JWT), protected route working end-to-end.
3. **Hour 10–20**: Market data service (Finnhub client), `price_snapshots` table, manual "fetch quote" endpoint working and verified against real data.
4. **Hour 20–30**: Watchlist CRUD (create list, add/remove symbol), wired to frontend dashboard — basic, unstyled, functional.
5. **Hour 30–42**: Change engine (§1.1) — price move, volume spike, sector deviation, confidence scoring. This is the differentiator, don't rush it. Background polling job for tracked symbols. Add company-news fetch (only for anomalous symbols) and store headlines.
6. **Hour 42–55**: Frontend polish — shadcn/ui components, change badges (🔴🟠🟡), confidence labels, sparkline, "since you last checked" header, staleness indicators. Match the home-page mock's grouping (attention items vs. "nothing meaningful changed" list).
7. **Hour 55–63**: Chat feature (§5) — guardrail pipeline first, then the endpoint, then the minimal UI panel. Keep it last-in-core-scope: it's a strong add-on but the dashboard must work without it.
8. **Hour 63–68**: Edge cases — stale data, conflicting snapshot handling, empty states, error states, responsive layout, chat rate-limit behavior.
9. **Hour 68–70**: README, design-decisions write-up, demo script/talking points.
10. **Hour 70–72**: Buffer. Submit well before the deadline — remember only the first 1,000 valid submissions are evaluated.

---

## 10. Next steps
- Send the exact PS wording if anything above needs re-reading against it once released in full.
- When ready to deploy, ask separately for the Render (backend) + Vercel (frontend) deployment doc — kept as its own file so it doesn't bloat this plan.
