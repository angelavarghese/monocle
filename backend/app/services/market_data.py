from datetime import datetime

import httpx

from app.core.config import settings


async def fetch_finnhub_quote(symbol: str) -> dict[str, float]:
    if not settings.finnhub_api_key:
        raise RuntimeError("FINNHUB_API_KEY is not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": symbol, "token": settings.finnhub_api_key},
        )
        response.raise_for_status()
        return response.json()


def quote_to_snapshot_values(quote: dict[str, float]) -> dict[str, float | datetime]:
    return {
        "price": quote.get("c", 0),
        "change_pct": quote.get("dp", 0),
        "volume": quote.get("v", 0),
        "fetched_at": datetime.utcnow(),
    }
