from datetime import datetime

from pydantic import BaseModel


class QuoteRead(BaseModel):
    symbol: str
    price: float
    change_pct: float | None
    volume: float
    fetched_at: datetime
    stale: bool


class HistoryPoint(BaseModel):
    price: float
    fetched_at: datetime
