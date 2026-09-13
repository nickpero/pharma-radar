"""Historical Edge Score V1 for Pharma Radar.

This module converts the persistent historical catalyst backtest into a
point-in-time, conservative historical-edge feature for live events.

It is descriptive/decision-support only: it does not generate buy/sell
signals and it never uses future live data. The historical dataset is loaded
lazily so unit tests and live scans remain safe if the optional files are
missing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SEGMENTS_FILE = Path("data/historical_edge_segments.json")
EDGE_FILE = Path("data/historical_edge.json")
WINDOW = "1D"
PRIOR_N = 20
MIN_TICKER_SAMPLE = 5
MAX_TICKER_ADJUSTMENT = 10.0
VERSION = "1.0"


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load(path: Path) -> dict[str, Any]:
    try:
        if not path.exists() or path.stat().st_size == 0:
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _window_stats(group: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(group, dict):
        return {}
    value = group.get(WINDOW)
    return value if isinstance(value, dict) else {}


def _shrink(value: float | None, n: int, prior: float | None, prior_n: int = PRIOR_N) -> float | None:
    if value is None:
        return prior
    weight = max(0.0, float(n)) / (max(0.0, float(n)) + prior_n)
    if prior is None:
        return value
    return value * weight + prior * (1.0 - weight)


def _score(median_ar: float | None, win_rate: float | None) -> float:
    """Map 1D directional edge to a conservative 0-100 score.

    50 is neutral. Positive median abnormal return and win rate above 50%
    raise the score; negative edge lowers it. The coefficients are deliberately
    transparent and are not optimized on the live sample.
    """
    if median_ar is None and win_rate is None:
        return 50.0
    median_component = 8.0 * (median_ar or 0.0)
    win_component = 80.0 * ((win_rate if win_rate is not None else 0.5) - 0.5)
    return max(0.0, min(100.0, 50.0 + median_component + win_component))


def _confidence(n: int) -> str:
    if n >= 25:
        return "HIGH"
    if n >= 10:
        return "MEDIUM"
    if n >= 5:
        return "LOW"
    return "UNKNOWN"


def _label(median_ar: float | None, win_rate: float | None) -> str:
    if median_ar is None or win_rate is None:
        return "UNKNOWN"
    if median_ar >= 3.0 and win_rate >= 0.60:
        return "STRONG_POSITIVE"
    if median_ar >= 1.0 and win_rate >= 0.55:
        return "POSITIVE"
    if median_ar <= -1.0 and win_rate <= 0.45:
        return "NEGATIVE"
    return "NEUTRAL"


def _global_stats(segments: dict[str, Any]) -> tuple[float | None, float | None, int]:
    stats = _window_stats(segments.get("summary"))
    return _num(stats.get("median_directional_ar_pct")), _num(stats.get("win_rate")), int(_num(stats.get("n")) or 0)


def calculate_historical_edge(event: dict[str, Any], segments: dict[str, Any] | None = None, edge_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Calculate the historical edge feature for one live catalyst."""
    event = dict(event or {})
    segments = segments if segments is not None else _load(SEGMENTS_FILE)
    edge_data = edge_data if edge_data is not None else _load(EDGE_FILE)

    global_median, global_win, global_n = _global_stats(segments)
    subtype = str(event.get("subtype") or "UNKNOWN").upper()
    direction = str(event.get("direction") or "UNKNOWN").upper()
    ticker = str(event.get("ticker") or "UNKNOWN").upper()

    subtype_stats = _window_stats((segments.get("by_subtype") or {}).get(subtype))
    subtype_n = int(_num(subtype_stats.get("n")) or 0)
    subtype_median = _num(subtype_stats.get("median_directional_ar_pct"))
    subtype_win = _num(subtype_stats.get("win_rate"))

    adj_median = _shrink(subtype_median, subtype_n, global_median)
    adj_win = _shrink(subtype_win, subtype_n, global_win)

    direction_stats = _window_stats((segments.get("by_direction") or {}).get(direction))
    direction_n = int(_num(direction_stats.get("n")) or 0)
    direction_median = _shrink(_num(direction_stats.get("median_directional_ar_pct")), direction_n, global_median)
    direction_win = _shrink(_num(direction_stats.get("win_rate")), direction_n, global_win)
    direction_adjustment = max(-8.0, min(8.0, _score(direction_median, direction_win) - _score(global_median, global_win)))

    ticker_stats = _window_stats((edge_data.get("by_ticker") or {}).get(ticker))
    ticker_n = int(_num(ticker_stats.get("n")) or 0)
    ticker_median = _num(ticker_stats.get("median_directional_abnormal_return_pct"))
    ticker_win = _num(ticker_stats.get("win_rate"))
    ticker_adj_median = _shrink(ticker_median, ticker_n, global_median)
    ticker_adj_win = _shrink(ticker_win, ticker_n, global_win)
    ticker_adjustment = 0.0
    if ticker_n >= MIN_TICKER_SAMPLE:
        ticker_adjustment = max(-MAX_TICKER_ADJUSTMENT, min(MAX_TICKER_ADJUSTMENT, _score(ticker_adj_median, ticker_adj_win) - _score(global_median, global_win)))

    base_score = _score(adj_median, adj_win)
    final_score = max(0.0, min(100.0, base_score + direction_adjustment + ticker_adjustment))

    return {
        "historical_edge_version": VERSION,
        "historical_edge_score": round(final_score, 1),
        "historical_edge_label": _label(adj_median, adj_win),
        "historical_edge_confidence": _confidence(subtype_n),
        "historical_edge_sample": subtype_n,
        "historical_edge_median_1d_pct": round(adj_median, 4) if adj_median is not None else None,
        "historical_edge_win_rate_1d": round(adj_win, 4) if adj_win is not None else None,
        "historical_edge_global_sample": global_n,
        "historical_edge_direction_adjustment": round(direction_adjustment, 1),
        "historical_edge_ticker_sample": ticker_n,
        "historical_edge_ticker_adjustment": round(ticker_adjustment, 1),
    }


def enrich_historical_edge(event: dict[str, Any], segments: dict[str, Any] | None = None, edge_data: dict[str, Any] | None = None) -> dict[str, Any]:
    result = dict(event or {})
    result.update(calculate_historical_edge(result, segments=segments, edge_data=edge_data))
    return result


def enrich_historical_edges(events: list[dict[str, Any]] | None, segments: dict[str, Any] | None = None, edge_data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [enrich_historical_edge(event, segments=segments, edge_data=edge_data) for event in (events or [])]
