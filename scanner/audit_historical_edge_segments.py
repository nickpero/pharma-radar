"""Segment and baseline-backtest the clean historical catalyst sample.

Research-only: this module does not generate trade recommendations. Returns are
already directionally oriented by catalyst direction in market_metrics.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

DATASET = Path("data/historical_catalyst_dataset.json")
OUTPUT = Path("data/historical_edge_segments.json")
WINDOWS = ("1D", "3D", "5D")


def _load() -> dict[str, Any]:
    if not DATASET.exists() or DATASET.stat().st_size == 0:
        return {}
    return json.loads(DATASET.read_text(encoding="utf-8"))


def _metric(event: dict[str, Any], window: str) -> float | None:
    row = ((event.get("market_metrics") or {}).get("windows") or {}).get(window) or {}
    value = row.get("directional_abnormal_return_pct")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _year(event: dict[str, Any]) -> str:
    text = str(event.get("event_timestamp") or "")
    try:
        return str(datetime.fromisoformat(text.replace("Z", "+00:00")).year)
    except ValueError:
        return text[:4] if len(text) >= 4 else "UNKNOWN"


def _summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"events": len(events)}
    for window in WINDOWS:
        values = [v for e in events if (v := _metric(e, window)) is not None]
        result[window] = {
            "n": len(values),
            "median_directional_ar_pct": median(values) if values else None,
            "mean_directional_ar_pct": sum(values) / len(values) if values else None,
            "win_rate": sum(v > 0 for v in values) / len(values) if values else None,
            "loss_rate": sum(v < 0 for v in values) / len(values) if values else None,
        }
    volumes = []
    for e in events:
        value = (e.get("market_metrics") or {}).get("volume_expansion")
        try:
            if value is not None:
                volumes.append(float(value))
        except (TypeError, ValueError):
            pass
    result["median_volume_expansion"] = median(volumes) if volumes else None
    return result


def _segments(events: list[dict[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        value = str(event.get(field) or "UNKNOWN").upper()
        groups.setdefault(value, []).append(event)
    return {key: _summary(groups[key]) for key in sorted(groups)}


def _year_segments(events: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        groups.setdefault(_year(event), []).append(event)
    return {key: _summary(groups[key]) for key in sorted(groups)}


def _size_bucket(event: dict[str, Any]) -> str:
    value = (event.get("market_metrics") or {}).get("market_cap")
    try:
        cap = float(value)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if cap < 2_000_000_000:
        return "SMALL_<2B"
    if cap < 10_000_000_000:
        return "MID_2B_10B"
    return "LARGE_>=10B"


def _size_segments(events: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        groups.setdefault(_size_bucket(event), []).append(event)
    return {key: _summary(groups[key]) for key in sorted(groups)}


def _baseline_backtest(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Idealized event-close baseline, without costs/slippage/position sizing."""
    result: dict[str, Any] = {
        "method": "event_close_to_future_close_directional_baseline",
        "costs_bps": 0,
        "slippage_bps": 0,
        "position_sizing": "1 unit per event, no portfolio overlap control",
        "windows": {},
    }
    for window in WINDOWS:
        values = [v for e in events if (v := _metric(e, window)) is not None]
        if not values:
            result["windows"][window] = {"n": 0}
            continue
        compounded = 1.0
        for value in values:
            compounded *= 1.0 + value / 100.0
        result["windows"][window] = {
            "n": len(values),
            "median_return_pct": median(values),
            "mean_return_pct": sum(values) / len(values),
            "win_rate": sum(v > 0 for v in values) / len(values),
            "arithmetic_sum_pct": sum(values),
            "compound_if_serial_pct": (compounded - 1.0) * 100.0,
            "max_single_gain_pct": max(values),
            "max_single_loss_pct": min(values),
        }
    return result


def build() -> dict[str, Any]:
    payload = _load()
    events = [e for e in (payload.get("tradable_catalysts") or []) if e.get("market_metrics")]
    ticker_counts = Counter(str(e.get("ticker") or "UNKNOWN") for e in events)
    top5 = ticker_counts.most_common(5)
    top5_n = sum(n for _, n in top5)
    result = {
        "version": "1.0",
        "methodology": {
            "purpose": "historical segmentation and sanity-check backtest",
            "directional_return": "directionally oriented abnormal return from event close",
            "windows": list(WINDOWS),
            "costs_and_slippage": "not modeled",
            "lookahead_warning": "descriptive historical analysis only; not a live trading rule",
        },
        "summary": _summary(events),
        "by_subtype": _segments(events, "subtype"),
        "by_direction": _segments(events, "direction"),
        "by_source": _segments(events, "source"),
        "by_year": _year_segments(events),
        "by_market_cap": _size_segments(events),
        "ticker_concentration": {
            "unique_tickers": len(ticker_counts),
            "top_5": dict(top5),
            "top_5_share": top5_n / len(events) if events else None,
            "counts": dict(ticker_counts.most_common()),
        },
        "baseline_backtest": _baseline_backtest(events),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    result = build()
    summary = result["summary"]
    print("========== HISTORICAL EDGE SEGMENTS ==========")
    print(f"Events with market metrics: {summary['events']}")
    for window in WINDOWS:
        print(f"{window}: median={summary[window]['median_directional_ar_pct']}% win={summary[window]['win_rate']}")
    print(f"By subtype: {result['by_subtype']}")
    print(f"By direction: {result['by_direction']}")
    print(f"By market cap: {result['by_market_cap']}")
    print(f"Top-5 ticker share: {result['ticker_concentration']['top_5_share']}")
    print("-- BASELINE BACKTEST --")
    for window, data in result["baseline_backtest"]["windows"].items():
        print(f"{window}: {data}")
    print("==============================================")
    if summary["events"] == 0:
        raise SystemExit("No market-matched tradable catalysts available")


if __name__ == "__main__":
    main()
