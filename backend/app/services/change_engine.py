from datetime import datetime

from app.core.config import settings
from app.models.snapshot import PriceSnapshot


def classify_change(
    current: PriceSnapshot | None,
    previous: PriceSnapshot | None,
    *,
    is_priority: bool = False,
    has_news: bool = False,
) -> dict[str, object]:
    if current is None:
        return {"status": "stale", "confidence": "Low", "reason": "No market data yet", "signals": []}

    signals: list[str] = []
    if previous and previous.price:
        delta_pct = ((current.price - previous.price) / previous.price) * 100
    else:
        delta_pct = current.change_pct or 0

    if abs(delta_pct) >= settings.price_move_threshold_pct:
        signals.append("price movement")
    if current.avg_volume_20d and current.volume >= current.avg_volume_20d * settings.volume_spike_multiplier:
        signals.append("unusual volume")
    if current.high_30d and current.price >= current.high_30d or current.low_30d and current.price <= current.low_30d:
        signals.append("30-day range breakout")
    if has_news:
        signals.append("company event")
    if is_priority and signals:
        signals.append("priority holding")

    age_minutes = (datetime.utcnow() - current.fetched_at).total_seconds() / 60
    if age_minutes > settings.stale_threshold_minutes:
        return {"status": "stale", "confidence": "Low", "reason": "Latest price is delayed", "signals": ["stale data"]}

    confidence = "High" if len(signals) >= 3 or (signals and has_news) else "Medium" if len(signals) == 2 else "Low"
    status = "significant" if len(signals) >= 3 else "notable" if signals else "quiet"
    if not signals:
        reason = "Nothing meaningful changed"
    else:
        direction = "rose" if delta_pct >= 0 else "fell"
        reason = f"{direction.capitalize()} {abs(delta_pct):.2f}% with " + " + ".join(signals)
    return {"status": status, "confidence": confidence, "reason": reason, "signals": signals}
