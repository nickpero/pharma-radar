"""Pharma Radar — Trading Setup scoring (Phase 4)."""

from datetime import datetime, timezone
import re


SETUP_MAX = 100


def _bounded(value, default=0):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _freshness_score(minutes):
    if minutes is None:
        return 0
    if minutes <= 15:
        return 15
    if minutes <= 60:
        return 12
    if minutes <= 240:
        return 8
    if minutes <= 1440:
        return 4
    return 0


def minutes_since(timestamp, now=None):
    """Return elapsed minutes for an ISO timestamp; None when unavailable."""
    if not timestamp:
        return None
    try:
        value = str(timestamp).replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        reference = now or datetime.now(timezone.utc)
        return max(0.0, (reference - dt).total_seconds() / 60.0)
    except (TypeError, ValueError):
        return None


def trading_window(minutes):
    """Classify the event inside the user's 7-day short-term window."""
    if minutes is None:
        return "UNKNOWN"
    if minutes <= 120:
        return "0-2H"
    if minutes <= 1440:
        return "2-24H"
    if minutes <= 10080:
        return "1-7D"
    return "EXPIRED"


def reaction_score(price_change_pct, direction="UNKNOWN"):
    """Score early price reaction without treating it as a buy/sell signal."""
    if price_change_pct is None:
        return 0
    move = abs(float(price_change_pct))
    score = min(10, round(move * 1.25))
    direction = str(direction or "UNKNOWN").upper()
    if direction == "POSITIVE" and price_change_pct < 0:
        return max(0, score - 3)
    if direction == "NEGATIVE" and price_change_pct > 0:
        return max(0, score - 3)
    return score


def volume_score(volume_ratio):
    if volume_ratio is None:
        return 0
    ratio = float(volume_ratio)
    if ratio >= 5:
        return 10
    if ratio >= 3:
        return 8
    if ratio >= 2:
        return 6
    if ratio >= 1.25:
        return 4
    return 2


def market_awareness(price_change_pct, volume_ratio):
    """Estimate how much the market has already reacted to the event."""
    if price_change_pct is None and volume_ratio is None:
        return "UNKNOWN"
    move = abs(float(price_change_pct or 0))
    volume = float(volume_ratio or 0)
    if move >= 10 or volume >= 5:
        return "HIGH"
    if move >= 5 or volume >= 3:
        return "MEDIUM"
    return "LOW"


def infer_event_surprise(event):
    """Infer surprise only from explicit expectation language; otherwise UNKNOWN."""
    event = dict(event or {})
    explicit = str(event.get("event_surprise") or "").upper()
    if explicit in {"UNEXPECTED", "EXPECTED", "MIXED"}:
        return explicit

    text = " ".join(
        str(event.get(key) or "")
        for key in ("title", "summary", "content", "description", "event_text")
    ).lower()
    if not text:
        return "UNKNOWN"

    unexpected = (
        r"\bunexpect(?:ed|edly)\b",
        r"\bsurpris(?:e|ing|ed)\b",
        r"\bahead of (?:expectations|consensus)\b",
        r"\bbeats? (?:expectations|consensus)\b",
        r"\babove (?:expectations|consensus)\b",
        r"\bbelow (?:expectations|consensus)\b",
        r"\bmiss(?:es|ed)? (?:expectations|consensus)\b",
    )
    expected = (
        r"\bin line with (?:expectations|consensus)\b",
        r"\bas expected\b",
        r"\bmet expectations\b",
        r"\bin line\b",
    )
    if any(re.search(pattern, text) for pattern in unexpected):
        return "UNEXPECTED"
    if any(re.search(pattern, text) for pattern in expected):
        return "EXPECTED"
    return "UNKNOWN"


def surprise_score(event_surprise):
    return {"UNEXPECTED": 7, "MIXED": 4, "EXPECTED": 1, "UNKNOWN": 0}.get(
        str(event_surprise or "UNKNOWN").upper(), 0
    )


def market_cap_score(market_cap):
    """Small-cap events receive more attention weight, not a directional signal."""
    if market_cap is None:
        return 0
    try:
        cap = float(market_cap)
    except (TypeError, ValueError):
        return 0
    if cap < 300_000_000:
        return 4
    if cap < 1_000_000_000:
        return 3
    if cap < 5_000_000_000:
        return 2
    return 1


def short_interest_score(short_interest_pct):
    if short_interest_pct is None:
        return 0
    try:
        value = float(short_interest_pct)
    except (TypeError, ValueError):
        return 0
    if value >= 20:
        return 4
    if value >= 10:
        return 3
    if value >= 5:
        return 2
    return 1


def build_trading_setup(event, market_data=None, now=None):
    """Build a deterministic 0-100 setup score from known information."""
    event = dict(event or {})
    market_data = market_data or event.get("market_data") or {}

    score = _bounded(event.get("score", 0))
    impact = str(event.get("trading_impact", "LOW")).upper()
    urgency = str(event.get("urgency", "LOW")).upper()
    confidence = str(event.get("match_confidence", "LOW")).upper()

    catalyst_component = round(score * 0.25)
    impact_component = {"EXTREME": 20, "HIGH": 15, "MEDIUM": 10, "LOW": 4}.get(impact, 4)
    urgency_component = {"IMMEDIATE": 15, "FAST": 11, "NORMAL": 6, "LOW": 2}.get(urgency, 2)
    confidence_component = {"HIGH": 10, "MEDIUM": 6, "LOW": 2}.get(confidence, 2)

    minutes = minutes_since(event.get("published_at") or event.get("event_timestamp"), now=now)
    freshness = _freshness_score(minutes)
    price_change = market_data.get("price_change_pct")
    volume_ratio = market_data.get("volume_ratio")

    surprise = infer_event_surprise(event)
    market_cap = event.get("market_cap")
    short_interest = event.get("short_interest_pct")

    total = catalyst_component + impact_component + urgency_component + confidence_component
    total += freshness + reaction_score(price_change, event.get("direction")) + volume_score(volume_ratio)
    total += surprise_score(surprise) + market_cap_score(market_cap) + short_interest_score(short_interest)
    total = min(SETUP_MAX, total)

    return {
        "trading_setup_score": total,
        "trading_window": trading_window(minutes),
        "minutes_since_event": round(minutes, 1) if minutes is not None else None,
        "freshness_score": freshness,
        "price_change_pct": price_change,
        "volume_ratio": volume_ratio,
        "market_awareness": market_awareness(price_change, volume_ratio),
        "event_surprise": surprise,
        "event_surprise_score": surprise_score(surprise),
        "market_cap": market_cap,
        "market_cap_score": market_cap_score(market_cap),
        "short_interest_pct": short_interest,
        "short_interest_score": short_interest_score(short_interest),
    }


def enrich_trading_setup(event, market_data=None, now=None):
    result = dict(event or {})
    result.update(build_trading_setup(result, market_data=market_data, now=now))
    return result


def enrich_trading_setups(events, market_data_by_ticker=None, now=None):
    if not events:
        return []
    market_data_by_ticker = market_data_by_ticker or {}
    return [
        enrich_trading_setup(
            event,
            market_data=market_data_by_ticker.get(str(event.get("ticker") or "").upper(), event.get("market_data")),
            now=now,
        )
        for event in events
    ]
