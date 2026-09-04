from datetime import datetime

from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ItemCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    is_priority: bool = False


class ItemUpdate(BaseModel):
    is_priority: bool


class ChangeSummary(BaseModel):
    status: str
    confidence: str
    reason: str
    signals: list[str]


class WatchlistItemRead(BaseModel):
    id: int
    symbol: str
    is_priority: bool
    price: float | None = None
    previous_price: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    avg_volume_20d: float | None = None
    fetched_at: datetime | None = None
    change: ChangeSummary

    model_config = {"from_attributes": True}


class WatchlistRead(BaseModel):
    id: int
    name: str
    last_viewed_at: datetime | None
    item_count: int
    items: list[WatchlistItemRead]

    model_config = {"from_attributes": True}
