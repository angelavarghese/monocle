from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.snapshot import PriceSnapshot, TrackedSymbol
from app.models.user import User
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.watchlist import ItemCreate, ItemUpdate, WatchlistCreate, WatchlistItemRead, WatchlistRead
from app.services.change_engine import classify_change

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def owned_watchlist(watchlist_id: int, user: User, db: Session) -> Watchlist:
    watchlist = db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.user_id == user.id))
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return watchlist


def item_response(item: WatchlistItem, db: Session) -> WatchlistItemRead:
    current = db.scalar(select(PriceSnapshot).where(PriceSnapshot.symbol == item.symbol).order_by(PriceSnapshot.fetched_at.desc()))
    previous = db.get(PriceSnapshot, item.last_seen_snapshot_id) if item.last_seen_snapshot_id else None
    if previous and current and previous.id == current.id:
        previous = db.scalar(
            select(PriceSnapshot)
            .where(PriceSnapshot.symbol == item.symbol, PriceSnapshot.id != current.id)
            .order_by(PriceSnapshot.fetched_at.desc())
        )
    change = classify_change(current, previous, is_priority=item.is_priority)
    return WatchlistItemRead(
        id=item.id,
        symbol=item.symbol,
        is_priority=item.is_priority,
        price=current.price if current else None,
        previous_price=previous.price if previous else None,
        change_pct=current.change_pct if current else None,
        volume=current.volume if current else None,
        avg_volume_20d=current.avg_volume_20d if current else None,
        fetched_at=current.fetched_at if current else None,
        change=change,
    )


@router.get("", response_model=list[WatchlistRead])
def list_watchlists(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WatchlistRead]:
    watchlists = list(db.scalars(select(Watchlist).where(Watchlist.user_id == user.id).order_by(Watchlist.created_at)))
    return [WatchlistRead(id=w.id, name=w.name, last_viewed_at=w.last_viewed_at, item_count=len(w.items), items=[]) for w in watchlists]


@router.post("", response_model=WatchlistRead, status_code=status.HTTP_201_CREATED)
def create_watchlist(payload: WatchlistCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WatchlistRead:
    watchlist = Watchlist(user_id=user.id, name=payload.name)
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    return WatchlistRead(id=watchlist.id, name=watchlist.name, last_viewed_at=None, item_count=0, items=[])


@router.get("/{watchlist_id}", response_model=WatchlistRead)
def get_watchlist(watchlist_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WatchlistRead:
    watchlist = owned_watchlist(watchlist_id, user, db)
    items = [item_response(item, db) for item in sorted(watchlist.items, key=lambda value: value.is_priority, reverse=True)]
    watchlist.last_viewed_at = datetime.utcnow()
    for item in watchlist.items:
        latest = db.scalar(select(PriceSnapshot).where(PriceSnapshot.symbol == item.symbol).order_by(PriceSnapshot.fetched_at.desc()))
        if latest:
            item.last_seen_snapshot_id = latest.id
    db.commit()
    return WatchlistRead(
        id=watchlist.id,
        name=watchlist.name,
        last_viewed_at=watchlist.last_viewed_at,
        item_count=len(watchlist.items),
        items=items,
    )


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(watchlist_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    watchlist = owned_watchlist(watchlist_id, user, db)
    db.delete(watchlist)
    db.commit()


@router.post("/{watchlist_id}/items", response_model=WatchlistItemRead, status_code=status.HTTP_201_CREATED)
def add_item(watchlist_id: int, payload: ItemCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WatchlistItemRead:
    watchlist = owned_watchlist(watchlist_id, user, db)
    symbol = payload.symbol.upper().strip()
    if db.scalar(select(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id, WatchlistItem.symbol == symbol)):
        raise HTTPException(status_code=409, detail="Symbol is already on this watchlist")
    item = WatchlistItem(watchlist_id=watchlist.id, symbol=symbol, is_priority=payload.is_priority)
    db.add(item)
    tracked = db.get(TrackedSymbol, symbol) or TrackedSymbol(symbol=symbol, ref_count=0)
    tracked.ref_count += 1
    db.add(tracked)
    db.commit()
    db.refresh(item)
    return item_response(item, db)


@router.patch("/{watchlist_id}/items/{item_id}", response_model=WatchlistItemRead)
def update_item(watchlist_id: int, item_id: int, payload: ItemUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WatchlistItemRead:
    owned_watchlist(watchlist_id, user, db)
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.id == item_id, WatchlistItem.watchlist_id == watchlist_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    item.is_priority = payload.is_priority
    db.commit()
    return item_response(item, db)


@router.delete("/{watchlist_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(watchlist_id: int, item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    owned_watchlist(watchlist_id, user, db)
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.id == item_id, WatchlistItem.watchlist_id == watchlist_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    tracked = db.get(TrackedSymbol, item.symbol)
    if tracked:
        tracked.ref_count = max(0, tracked.ref_count - 1)
    db.delete(item)
    db.commit()
