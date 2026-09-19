"""Pharma Radar — Divergence Monitor V1.0.

Identifies strong positive-catalyst / negative-market-reaction divergences.
This is an informational research alert, not a trading signal.
"""

from __future__ import annotations


def _num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def classify_divergence(alert, threshold_pct=2.0):
    direction = str(alert.get("direction") or "").upper()
    if direction not in {"POSITIVE", "CATALYST"}:
        return None

    market_data = alert.get("market_data") or {}
    daily_pct = _num(alert.get("price_change_pct"))
    if daily_pct is None:
        daily_pct = _num(market_data.get("price_change_pct"))

    market_status = str(alert.get("trading_intelligence_market_status") or "").upper()
    if daily_pct is None or daily_pct > -abs(threshold_pct):
        return None
    if market_status != "DIVERGENT":
        return None

    return {
        "ticker": str(alert.get("ticker", "UNKNOWN")).upper(),
        "program": alert.get("program", "UNKNOWN"),
        "direction": direction,
        "daily_pct": daily_pct,
        "threshold_pct": abs(threshold_pct),
        "status": "DIVERGENT",
        "catalyst_score": alert.get("score", (alert.get("event") or {}).get("score", 0)),
        "trading_intelligence_score": alert.get("trading_intelligence_score"),
        "historical_edge_median_1d_pct": alert.get("historical_edge_median_1d_pct"),
        "historical_edge_win_rate_1d": alert.get("historical_edge_win_rate_1d"),
    }


def detect_divergences(alerts, threshold_pct=2.0):
    return [
        result
        for alert in (alerts or [])
        if (result := classify_divergence(alert, threshold_pct)) is not None
    ]
