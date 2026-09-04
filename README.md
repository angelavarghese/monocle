# Monocle

Monocle is a smart market watchlist that reads the fine print of the market. It does not treat every price tick as news: a holding becomes meaningful when unusual price movement, volume, a range breakout, a company event, priority, or stale data gives the user a reason to look closer. The dashboard separates attention items from holdings where nothing meaningful changed.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js App Router, TypeScript, CSS, Lucide |
| Backend | FastAPI, Pydantic, SQLAlchemy |
| Database | PostgreSQL in deployment, SQLite for local smoke testing |
| Market data | Finnhub quote and news APIs |
| Auth | JWT and password hashing |
| AI assistant | Groq, scoped to watchlist data |

## Prerequisites

- Node.js 20 or newer and npm
- Python 3.12 or newer
- PostgreSQL installed locally, or Docker if you add a local database container
- A free [Finnhub API key](https://finnhub.io/register) for quotes and company news
- A free [Groq API key](https://console.groq.com/keys) for the chat assistant

## Setup: Database

Create a PostgreSQL database named `smart_watchlist`:

```sql
CREATE DATABASE smart_watchlist;
```

For a quick local smoke test, leave `DATABASE_URL` unset. The backend defaults to `sqlite:///./monocle.db` and creates its tables on startup.

## Setup: Backend

```powershell
cd backend
..\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Set `DATABASE_URL`, `JWT_SECRET_KEY`, and `FINNHUB_API_KEY` in `.env`. `GROQ_API_KEY` is only needed when the chat endpoint is enabled. The API is available at `http://localhost:8000`; interactive Swagger documentation is at `/docs`.

## Setup: Frontend

```powershell
cd frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

The dashboard is available at `http://localhost:3000`. The first dashboard slice reads the first authenticated watchlist, displays meaningful changes, and supports adding symbols. Register and log in through the API, then store the returned access token in browser local storage under `monocle_token` for this hackathon-scoped client.

## Running Both Together

Run the backend on port `8000` and the frontend on port `3000`. The frontend uses `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1`. The backend's Swagger UI at `/docs` is intentionally available for judges to inspect and exercise the API directly.

## Design Decisions

- Meaningful change is computed from multiple corroborating signals rather than a raw ticker delta.
- Every quote is an immutable `price_snapshots` row, so a watchlist can compare against the exact snapshot seen during the previous detail visit.
- Watchlist reads mark `last_viewed_at` only when the detail view is opened, not during background polling.
- Tracked symbols use a reference count so one polling cycle can fetch a symbol once for many users.
- The local fallback is SQLite to make the first run fast; PostgreSQL remains the intended shared database.
- The frontend stores a JWT in memory/local storage only for the hackathon. Production would use an httpOnly cookie through a backend-for-frontend.

## What I'd Do With More Time

Add Redis for a hot-price cache, move polling to a durable task queue, use websocket updates instead of polling, add multi-provider market-data fallback, complete the company-news ingestion and Groq guardrail pipeline, and add Alembic migrations plus end-to-end browser tests.
