from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrackedSymbol(Base):
    __tablename__ = "tracked_symbols"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ref_count: Mapped[int] = mapped_column(Integer, default=0)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    price: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0)
    high_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    low_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_volume_20d: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    flagged_conflict: Mapped[bool] = mapped_column(Boolean, default=False)


class NewsHeadline(Base):
    __tablename__ = "news_headlines"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    headline: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(120))
    published_at: Mapped[datetime] = mapped_column(DateTime)
    linked_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("price_snapshots.id"), nullable=True)
