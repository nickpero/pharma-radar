"""
Pharma Radar — Market Data

Lightweight market snapshot and intraday reaction provider used by Trading Intelligence.
No trading action is performed here.
"""

from datetime import datetime, timedelta, timezone

import requests

from scanner.market_profile import get_market_profile


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
REQUEST_TIMEOUT = 10
USER_AGENT = "PharmaRadar/1.0"
INTRADAY_RANGE = "5d"
INTRADAY_INTERVAL = "1m"
REACTION_WINDOWS_MINUTES = (1, 5, 15, 30, 60)


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _parse_dt(value):
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        # A date-only value is deliberately not sufficient for intraday
        # reaction measurement: anchoring it at 00:00 can create fake moves.
        if not any(separator in text for separator in ("T", " ")):
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_market_snapshot(ticker, session=None):
    """Return a best-effort daily market snapshot for a US ticker."""
    ticker = str(ticker or "").strip().upper()
    if not ticker or ticker in {"UNKNOWN", "N/A"}:
        return None

    client = session or requests
    url = YAHOO_CHART_URL.format(ticker=ticker)
    params = {"range": "1mo", "interval": "1d", "events": "history"}
    try:
        response = client.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return None

    try:
        result = payload["chart"]["result"][0]
        meta = result.get("meta", {})
        indicators = result.get("indicators", {})
        quote = indicators.get("quote", [{}])[0]
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        current = _safe_float(meta.get("regularMarketPrice"))
        previous = _safe_float(meta.get("previousClose"))
        if current is None and closes:
            current = _safe_float(closes[-1])
        if previous is None and len(closes) >= 2:
            previous = _safe_float(closes[-2])

        volume = _safe_float(volumes[-1]) if volumes else None
        avg_volume = _mean([_safe_float(v) for v in volumes[-21:-1]])

        change_pct = None
        if current is not None and previous:
            change_pct = (current - previous) / previous * 100.0

        volume_ratio = None
        if volume is not None and avg_volume:
            volume_ratio = volume / avg_volume

        return {
            "ticker": ticker,
            "price": current,
            "previous_close": previous,
            "price_change_pct": change_pct,
            "volume": volume,
            "average_volume_20d": avg_volume,
            "volume_ratio": volume_ratio,
            "market_data_source": "YAHOO_CHART",
            "market_data_timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def get_intraday_series(ticker, session=None, range_=INTRADAY_RANGE, interval=INTRADAY_INTERVAL):
    """Return timestamped intraday OHLCV points, best effort."""
    ticker = str(ticker or "").strip().upper()
    if not ticker or ticker in {"UNKNOWN", "N/A"}:
        return []
    client = session or requests
    try:
        response = client.get(
            YAHOO_CHART_URL.format(ticker=ticker),
            params={"range": range_, "interval": interval, "events": "history"},
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])
        points = []
        for i, timestamp in enumerate(timestamps):
            close = _safe_float(closes[i]) if i < len(closes) else None
            if close is None:
                continue
            volume = _safe_float(volumes[i]) if i < len(volumes) else None
            points.append({
                "timestamp": datetime.fromtimestamp(int(timestamp), tz=timezone.utc),
                "price": close,
                "volume": volume,
            })
        return points
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError, OverflowError):
        return []


def _pct_change(start, end):
    if start is None or end is None or start == 0:
        return None
    return (end - start) / start * 100.0


def _nearest_price(points, target, prefer_after=False):
    candidates = [p for p in points if (p["timestamp"] >= target if prefer_after else p["timestamp"] <= target)]
    if not candidates:
        return None
    return min(candidates, key=lambda p: abs((p["timestamp"] - target).total_seconds()))


def build_market_reaction(points, event_timestamp, now=None, previous_close=None):
    """Build price/volume reaction metrics around a catalyst timestamp."""
    event_dt = _parse_dt(event_timestamp)
    if event_dt is None or not points:
        return {
            "reaction_status": "UNAVAILABLE",
            "reaction_direction": "UNKNOWN",
            "reaction_source": "YAHOO_INTRADAY",
        }

    points = sorted(points, key=lambda p: p["timestamp"])
    reference_now = _parse_dt(now) if now is not None else datetime.now(timezone.utc)
    if reference_now is None:
        reference_now = datetime.now(timezone.utc)
    event_point = _nearest_price(points, event_dt, prefer_after=True)
    current_point = _nearest_price(points, reference_now)
    if event_point is None or current_point is None:
        return {
            "reaction_status": "UNAVAILABLE",
            "reaction_direction": "UNKNOWN",
            "reaction_source": "YAHOO_INTRADAY",
        }

    # Do not manufacture an event price from a bar that is materially later
    # than the catalyst. This protects all downstream 1/5/15/30/60m outcomes.
    anchor_delay = (event_point["timestamp"] - event_dt).total_seconds()
    if anchor_delay < 0 or anchor_delay > 5 * 60:
        return {
            "reaction_status": "UNAVAILABLE",
            "reaction_direction": "UNKNOWN",
            "reaction_source": "YAHOO_INTRADAY",
        }

    event_price = event_point["price"]
    current_price = current_point["price"]
    reaction = {
        "reaction_status": "AVAILABLE",
        "reaction_source": "YAHOO_INTRADAY",
        "event_price": event_price,
        "current_price": current_price,
        "reaction_pct": _pct_change(event_price, current_price),
        "reaction_direction": (
            "POSITIVE" if current_price > event_price else
            "NEGATIVE" if current_price < event_price else "FLAT"
        ),
        "event_timestamp": event_point["timestamp"].isoformat(),
        "reaction_timestamp": current_point["timestamp"].isoformat(),
    }

    pre_point = _nearest_price(points, event_dt - timedelta(minutes=15))
    reaction["pre_event_15m_pct"] = _pct_change(
        pre_point["price"] if pre_point else None, event_price
    )

    post_points = [p for p in points if event_point["timestamp"] <= p["timestamp"] <= current_point["timestamp"]]
    prices = [p["price"] for p in post_points if p.get("price") is not None]
    reaction["post_catalyst_high"] = max(prices) if prices else None
    reaction["post_catalyst_low"] = min(prices) if prices else None
    reaction["gap_pct"] = _pct_change(previous_close, event_price)

    for minutes in REACTION_WINDOWS_MINUTES:
        target = event_point["timestamp"] + timedelta(minutes=minutes)
        point = _nearest_price(points, target)
        if point is None or point["timestamp"] < event_point["timestamp"]:
            reaction[f"reaction_{minutes}m_pct"] = None
        else:
            reaction[f"reaction_{minutes}m_pct"] = _pct_change(event_price, point["price"])

    volumes = [p.get("volume") for p in post_points if p.get("volume") not in (None, 0)]
    reaction["event_volume"] = event_point.get("volume")
    reaction["post_event_volume"] = sum(volumes) if volumes else None
    return reaction


def get_market_reaction(ticker, event_timestamp, session=None, now=None, previous_close=None):
    """Fetch intraday data and calculate the reaction to a catalyst."""
    points = get_intraday_series(ticker, session=session)
    return build_market_reaction(points, event_timestamp, now=now, previous_close=previous_close)


def enrich_market_data(events):
    """Add market snapshot plus market profile to each event, best effort."""
    if not events:
        return []

    cache = {}
    profile_cache = {}
    enriched = []
    for event in events:
        result = dict(event)
        ticker = str(result.get("ticker") or "").upper()
        if ticker and ticker not in cache:
            cache[ticker] = get_market_snapshot(ticker)
        snapshot = cache.get(ticker)
        if snapshot:
            result["market_data"] = snapshot

        if ticker and ticker not in profile_cache:
            profile_cache[ticker] = get_market_profile(ticker)
        profile = profile_cache.get(ticker)
        if profile:
            result["market_profile"] = profile
            result["market_cap"] = profile.get("market_cap")
            result["short_interest_pct"] = profile.get("short_interest_pct")
        enriched.append(result)
    return enriched


def enrich_market_reactions(events, now=None):
    """Add intraday reaction data to events, caching one series per ticker."""
    if not events:
        return []
    cache = {}
    enriched = []
    for event in events:
        result = dict(event)
        ticker = str(result.get("ticker") or "").strip().upper()
        timestamp = result.get("event_timestamp") or result.get("published_at") or result.get("timestamp")
        if ticker and ticker not in cache:
            cache[ticker] = get_intraday_series(ticker)
        points = cache.get(ticker, [])
        snapshot = result.get("market_data") or {}
        result["market_reaction"] = build_market_reaction(
            points,
            timestamp,
            now=now,
            previous_close=snapshot.get("previous_close"),
        )
        enriched.append(result)
    return enriched
