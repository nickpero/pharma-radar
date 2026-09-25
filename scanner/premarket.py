"""Pharma Opportunity Radar — pre-market scoring and Telegram report."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from scanner.telegram import send_telegram

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
WATCHLIST_FILE = Path("data/watchlist.json")
HISTORY_FILE = Path("data/catalyst_history.json")
STATE_FILE = Path("data/premarket_state.json")
ROME = ZoneInfo("Europe/Rome")
REQUEST_TIMEOUT = 10
MAX_CANDIDATES = 5


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load(path, fallback):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, TypeError):
        return fallback


def _timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=dt.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def get_premarket_snapshot(ticker, session=None):
    """Best-effort extended-hours quote using Yahoo chart data."""
    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return None
    client = session or requests
    params = {"range": "1d", "interval": "1m", "events": "history", "includePrePost": "true"}
    try:
        response = client.get(
            YAHOO_CHART_URL.format(ticker=ticker),
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "PharmaRadar/1.0"},
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        meta = result.get("meta", {})
        previous = _float(meta.get("previousClose"))
        price = _float(meta.get("preMarketPrice"))
        change = _float(meta.get("preMarketChangePercent"))
        volume = _float(meta.get("preMarketVolume"))

        if change is None and price is not None and previous:
            change = (price - previous) / previous * 100.0

        return {
            "ticker": ticker,
            "previous_close": previous,
            "premarket_price": price,
            "premarket_change_pct": change,
            "premarket_volume": volume,
            "source": "YAHOO_CHART_EXTENDED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError):
        return None


def recent_catalysts(max_age_hours=24):
    data = _load(HISTORY_FILE, [])
    if isinstance(data, dict):
        data = data.get("events") or data.get("history") or data.get("records") or []
    now = datetime.now(timezone.utc)
    rows = []
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        dt = _timestamp(row.get("event_timestamp") or row.get("published_at") or row.get("timestamp"))
        if dt is None or now - dt > timedelta(hours=max_age_hours) or dt > now + timedelta(minutes=5):
            continue
        item = dict(row)
        item["_ts"] = dt
        rows.append(item)
    rows.sort(key=lambda x: x["_ts"], reverse=True)
    return rows


def _confidence(row):
    return {"CONFIRMED": 20, "PROBABLE": 12, "UNCONFIRMED": 5, "CONTRADICTED": 0}.get(
        str(row.get("catalyst_confirmation") or row.get("catalyst_confidence") or "").upper(), 4
    )


def _timing(row, now):
    age = now - row.get("_ts", now)
    if age <= timedelta(hours=3):
        return 10
    if age <= timedelta(hours=8):
        return 8
    if age <= timedelta(hours=16):
        return 6
    if age <= timedelta(hours=24):
        return 3
    return 0


def _movement(value):
    value = abs(_float(value) or 0)
    return 10 if value >= 50 else 8 if value >= 25 else 6 if value >= 15 else 4 if value >= 8 else 2 if value >= 3 else 0


def score_opportunity(catalyst, snapshot, now=None):
    now = now or datetime.now(timezone.utc)
    catalyst = catalyst or {}
    snapshot = snapshot or {}
    catalyst_score = min(30, (_float(catalyst.get("score") or catalyst.get("catalyst_score")) or 0) * 0.30)
    impact = min(15, (_float(catalyst.get("market_impact_score")) or 0) * 0.15)
    novelty = min(10, (_float(catalyst.get("novelty_score")) or 0) * 0.10)
    surprise = {"VERY_HIGH": 5, "HIGH": 5, "MODERATE": 3, "MIXED": 2}.get(str(catalyst.get("event_surprise") or "").upper(), 0)
    components = {
        "catalyst": catalyst_score,
        "confidence": _confidence(catalyst) if catalyst else 0,
        "clinical_impact": impact,
        "novelty": novelty,
        "timing": _timing(catalyst, now) if catalyst else 0,
        "market_movement": _movement(snapshot.get("premarket_change_pct")),
        "surprise": surprise,
    }
    return min(100, round(sum(components.values()))), components


def build_candidates(now=None, session=None):
    now = now or datetime.now(timezone.utc)
    watchlist = _load(WATCHLIST_FILE, {})
    best = {}
    for row in recent_catalysts():
        ticker = str(row.get("ticker") or "").upper()
        if ticker and ticker not in best:
            best[ticker] = row

    candidates = []
    for ticker, company in watchlist.items():
        catalyst = best.get(str(ticker).upper(), {})
        snapshot = get_premarket_snapshot(ticker, session=session) or {}
        score, components = score_opportunity(catalyst, snapshot, now)
        programs = company.get("programs") or ["N/A"]
        candidates.append({
            "ticker": str(ticker).upper(),
            "company": company.get("company", ticker),
            "program": catalyst.get("program") or programs[0],
            "catalyst": catalyst,
            "snapshot": snapshot,
            "opportunity_score": score,
            "components": components,
            "confidence": str(catalyst.get("catalyst_confirmation") or catalyst.get("catalyst_confidence") or "UNCONFIRMED").upper(),
        })
    candidates.sort(key=lambda x: (x["opportunity_score"], abs(_float(x["snapshot"].get("premarket_change_pct")) or 0)), reverse=True)
    return candidates[:MAX_CANDIDATES]


def format_report(candidates, phase="FINAL", now=None):
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(ROME)
    lines = [
        "🚨 PHARMA OPPORTUNITY RADAR",
        "━━━━━━━━━━━━━━━━━━",
        f"🇺🇸 PRE-MARKET · {phase}",
        f"🕐 {local.strftime('%H:%M')} Europe/Rome",
        "",
    ]
    for i, item in enumerate(candidates, 1):
        change = item["snapshot"].get("premarket_change_pct")
        change_text = f"{change:+.1f}%" if change is not None else "N/A"
        catalyst = item["catalyst"]
        title = catalyst.get("title") or catalyst.get("subtype") or "No confirmed catalyst"
        lines += [
            f"{i}. {'🔴' if item['opportunity_score'] >= 80 else '🟠' if item['opportunity_score'] >= 60 else '🟡' if item['opportunity_score'] >= 40 else '⚪'} {item['ticker']} · {item['opportunity_score']}/100",
            f"💊 {item['company']} · {item['program']}",
            f"⚡ {title}",
            f"🧠 Confidence: {item['confidence']}",
            f"📈 Pre-market: {change_text}",
            f"🔎 Source: {catalyst.get('source') or 'MARKET DATA'}",
            "",
        ]
    lines += [
        "━━━━━━━━━━━━━━━━━━",
        "ℹ️ Opportunity Score = monitoring priority, not a buy/sell signal.",
        "⚠️ Pre-market can be less liquid and more volatile than regular trading.",
    ]
    return "\n".join(lines)


def run(phase="FINAL", send=True, now=None):
    now = now or datetime.now(timezone.utc)
    candidates = build_candidates(now=now)
    report = format_report(candidates, phase, now)
    print(report)
    local = now.astimezone(ROME)
    if send and phase.upper() == "FINAL" and local.hour == 14 and 5 <= local.minute <= 25:
        state = _load(STATE_FILE, {})
        key = f"{local.date().isoformat()}:{','.join(x['ticker'] for x in candidates)}"
        if state.get("final_key") != key:
            state["final_key"] = key
            state["last_final_at"] = now.isoformat()
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
            send_telegram(report)
            return {"sent": True, "candidates": candidates}
    return {"sent": False, "candidates": candidates}


if __name__ == "__main__":
    run(phase=os.getenv("PHARMA_OPPORTUNITY_PHASE", "FINAL"), send=True)
