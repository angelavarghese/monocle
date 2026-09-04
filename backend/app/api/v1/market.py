from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.snapshot import PriceSnapshot
from app.schemas.market import HistoryPoint, QuoteRead
from app.core.config import settings

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/{symbol}/history", response_model=list[HistoryPoint])
def history(symbol: str, db: Session = Depends(get_db)) -> list[HistoryPoint]:
    snapshots = db.scalars(select(PriceSnapshot).where(PriceSnapshot.symbol == symbol.upper()).order_by(PriceSnapshot.fetched_at.desc()).limit(30))
    return [HistoryPoint(price=s.price, fetched_at=s.fetched_at) for s in reversed(list(snapshots))]


@router.get("/{symbol}/quote", response_model=QuoteRead)
def quote(symbol: str, db: Session = Depends(get_db)) -> QuoteRead:
    snapshot = db.scalar(select(PriceSnapshot).where(PriceSnapshot.symbol == symbol.upper()).order_by(PriceSnapshot.fetched_at.desc()))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot found for symbol")
    age = (datetime.utcnow() - snapshot.fetched_at).total_seconds() / 60
    return QuoteRead(symbol=snapshot.symbol, price=snapshot.price, change_pct=snapshot.change_pct, volume=snapshot.volume, fetched_at=snapshot.fetched_at, stale=age > settings.stale_threshold_minutes)
