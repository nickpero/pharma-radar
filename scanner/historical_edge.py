"""Historical Edge Engine — pure event/market reaction calculations.

This module intentionally contains no network or broker logic. It converts a
single catalyst event plus normalized price/volume observations into
benchmark-adjusted reaction metrics, then aggregates those metrics by catalyst
type/program/company.

It is an analytics layer, not a buy/sell signal generator.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

WINDOWS = ("1D", "3D", "5D")


def safe_return(start_price: float | None, end_price: float | None) -> float | None:
    try:
        start = float(start_price)  # type: ignore[arg-type]
        end = float(end_price)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if start <= 0:
        return None
    return (end / start - 1.0) * 100.0


def abnormal_return(stock_return: float | None, benchmark_return: float | None, beta: float = 1.0) -> float | None:
    if stock_return is None or benchmark_return is None:
        return None
    try:
        return float(stock_return) - float(beta) * float(benchmark_return)
    except (TypeError, ValueError):
        return None


def directional_return(abnormal: float | None, direction: str | None) -> float | None:
    """Orient abnormal return so positive means the market moved as expected."""
    if abnormal is None:
        return None
    if str(direction or "").upper() == "NEGATIVE":
        return -float(abnormal)
    return float(abnormal)


def volume_expansion(event_volume: float | None, baseline_volume: float | None) -> float | None:
    try:
        event = float(event_volume)  # type: ignore[arg-type]
        baseline = float(baseline_volume)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if baseline <= 0:
        return None
    return event / baseline


def confidence_for_sample(n: int) -> str:
    if n >= 25:
        return "HIGH"
    if n >= 10:
        return "MEDIUM"
    return "LOW"


def classify_edge(median_return: float | None, win_rate: float | None, n: int) -> str:
    if median_return is None or win_rate is None or n < 5:
        return "NEUTRAL"
    if median_return >= 3.0 and win_rate >= 0.60:
        return "POSITIVE"
    if median_return <= -3.0 and win_rate <= 0.40:
        return "NEGATIVE"
    return "NEUTRAL"


def _get_price(bar: Mapping[str, Any]) -> float | None:
    return bar.get("close") if "close" in bar else bar.get("price")


def _get_window_price(bars: Mapping[str, Mapping[str, Any]], window: str) -> float | None:
    item = bars.get(window)
    return _get_price(item) if item else None


def calculate_event_metrics(
    event: Mapping[str, Any],
    bars: Mapping[str, Mapping[str, Any]],
    benchmark_bars: Mapping[str, Mapping[str, Any]] | None = None,
    beta: float = 1.0,
) -> dict[str, Any]:
    event_bar = bars.get("event", {})
    event_price = _get_price(event_bar)
    event_volume = event_bar.get("volume")
    baseline_volume = event_bar.get("baseline_volume")
    direction = event.get("direction") or "UNKNOWN"

    metrics: dict[str, Any] = {
        "ticker": event.get("ticker"),
        "company": event.get("company"),
        "program": event.get("program"),
        "subtype": event.get("subtype") or event.get("event_type"),
        "direction": direction,
        "source": event.get("source"),
        "source_type": event.get("source_type"),
        "url": event.get("url"),
        "event_id": event.get("event_id") or event.get("memory_key") or event.get("source_item_id") or event.get("url"),
        "event_timestamp": event.get("event_timestamp") or event.get("timestamp"),
        "event_price": event_price,
        "volume_expansion": volume_expansion(event_volume, baseline_volume),
        "windows": {},
    }

    for window in WINDOWS:
        stock_return = safe_return(event_price, _get_window_price(bars, window))
        benchmark_return = (
            safe_return(_get_price(benchmark_bars.get("event", {})), _get_window_price(benchmark_bars, window))
            if benchmark_bars
            else None
        )
        abnormal = abnormal_return(stock_return, benchmark_return, beta)
        metrics["windows"][window] = {
            "stock_return_pct": stock_return,
            "benchmark_return_pct": benchmark_return,
            "abnormal_return_pct": abnormal,
            "directional_abnormal_return_pct": directional_return(abnormal, direction),
        }

    return metrics


def aggregate_historical_edge(metrics: Iterable[Mapping[str, Any]], group_by: str = "subtype") -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in metrics:
        key = item.get(group_by) or "UNKNOWN"
        groups[str(key)].append(item)

    result: dict[str, dict[str, Any]] = {}
    for key, items in groups.items():
        window_stats: dict[str, Any] = {}
        for window in WINDOWS:
            values = [item.get("windows", {}).get(window, {}).get("directional_abnormal_return_pct") for item in items]
            values = [float(value) for value in values if value is not None]
            wins = sum(value > 0 for value in values)
            n = len(values)
            med = median(values) if values else None
            win_rate = (wins / n) if n else None
            window_stats[window] = {
                "n": n,
                "median_directional_abnormal_return_pct": med,
                "median_abnormal_return_pct": med,
                "win_rate": win_rate,
                "edge": classify_edge(med, win_rate, n),
                "confidence": confidence_for_sample(n),
            }
        result[key] = {"group": key, "events": len(items), "windows": window_stats}
    return result


def build_historical_edge(events: Sequence[Mapping[str, Any]], market_data_provider: Any, benchmark: str = "XBI") -> dict[str, Any]:
    metrics = []
    for event in events:
        bars = market_data_provider.get_event_bars(event)
        benchmark_bars = market_data_provider.get_benchmark_bars(event, benchmark)
        item = calculate_event_metrics(event, bars, benchmark_bars)
        event_date = market_data_provider._event_date(event) if hasattr(market_data_provider, "_event_date") else None
        item["market_data_source"] = (
            market_data_provider.source_for(event.get("ticker"), event_date)
            if hasattr(market_data_provider, "source_for")
            else "UNKNOWN"
        )
        item["market_data_available"] = bool(item.get("event_price")) and all(
            item.get("windows", {}).get(window, {}).get("stock_return_pct") is not None
            for window in WINDOWS
        )
        metrics.append(item)
    output = {
        "benchmark": benchmark,
        "events": metrics,
        "by_subtype": aggregate_historical_edge(metrics, "subtype"),
        "by_ticker": aggregate_historical_edge(metrics, "ticker"),
    }
    if hasattr(market_data_provider, "stats"):
        output["market_data"] = market_data_provider.stats()
    return output
