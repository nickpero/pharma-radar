"""Pharma Radar — robust historical catalyst backtest V1.

Research-only validation layer. Uses the already directionally-oriented abnormal
returns in the historical catalyst dataset; it does not place trades or create
buy/sell recommendations.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

DATASET = Path("data/historical_catalyst_dataset.json")
OUTPUT = Path("data/robust_historical_backtest.json")
WINDOWS = ("1D", "3D", "5D")
MIN_SEGMENT_N = 30
DEFAULT_COST_BPS = 20.0
DEFAULT_SLIPPAGE_BPS = 10.0


def _load() -> dict[str, Any]:
    return json.loads(DATASET.read_text(encoding="utf-8"))


def _metric(event: dict[str, Any], window: str) -> float | None:
    row = ((event.get("market_metrics") or {}).get("windows") or {}).get(window) or {}
    try:
        return float(row["directional_abnormal_return_pct"])
    except (KeyError, TypeError, ValueError):
        return None


def _timestamp(event: dict[str, Any]) -> str:
    return str(event.get("event_timestamp") or "")


def _stats(values: list[float], friction_bps: float) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    friction_pct = friction_bps / 100.0
    net = [v - friction_pct for v in values]
    wins = [v for v in net if v > 0]
    losses = [v for v in net if v < 0]
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for value in net:
        equity *= 1.0 + value / 100.0
        peak = max(peak, equity)
        if peak:
            max_dd = min(max_dd, equity / peak - 1.0)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "n": len(net),
        "median_net_return_pct": median(net),
        "mean_net_return_pct": sum(net) / len(net),
        "win_rate": len(wins) / len(net),
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "compound_serial_pct": (equity - 1.0) * 100.0,
        "max_drawdown_pct": max_dd * 100.0,
        "max_gain_pct": max(net),
        "max_loss_pct": min(net),
    }


def _segment(events: list[dict[str, Any]], field: str, value: str) -> list[dict[str, Any]]:
    return [e for e in events if str(e.get(field) or "UNKNOWN").upper() == value]


def _segment_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    friction = DEFAULT_COST_BPS + DEFAULT_SLIPPAGE_BPS
    result: dict[str, Any] = {}
    for window in WINDOWS:
        values = [v for e in events if (v := _metric(e, window)) is not None]
        result[window] = _stats(values, friction)
    return result


def _leave_one_ticker_out(events: list[dict[str, Any]], window: str) -> dict[str, Any]:
    tickers = Counter(str(e.get("ticker") or "UNKNOWN") for e in events)
    baseline = [v for e in events if (v := _metric(e, window)) is not None]
    baseline_stats = _stats(baseline, DEFAULT_COST_BPS + DEFAULT_SLIPPAGE_BPS)
    rows = []
    for ticker, count in tickers.most_common():
        values = [v for e in events if str(e.get("ticker") or "UNKNOWN") != ticker and (v := _metric(e, window)) is not None]
        stats = _stats(values, DEFAULT_COST_BPS + DEFAULT_SLIPPAGE_BPS)
        rows.append({"excluded_ticker": ticker, "excluded_events": count, **stats})
    return {"baseline": baseline_stats, "exclusions": rows}


def _qualifying_segments(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[tuple[str, str, list[dict[str, Any]]]] = []
    fields = ("subtype", "source", "direction")
    for field in fields:
        values = sorted({str(e.get(field) or "UNKNOWN").upper() for e in events})
        for value in values:
            candidates.append((field, value, _segment(events, field, value)))
    out = []
    friction = DEFAULT_COST_BPS + DEFAULT_SLIPPAGE_BPS
    for field, value, group in candidates:
        vals = [v for e in group if (v := _metric(e, "1D")) is not None]
        if len(vals) < MIN_SEGMENT_N:
            continue
        stats = _stats(vals, friction)
        if stats["median_net_return_pct"] >= 1.0 and stats["win_rate"] >= 0.55:
            out.append({"field": field, "value": value, **stats})
    return out


def build() -> dict[str, Any]:
    payload = _load()
    events = [e for e in (payload.get("tradable_catalysts") or []) if e.get("market_metrics")]
    events.sort(key=_timestamp)
    ticker_counts = Counter(str(e.get("ticker") or "UNKNOWN") for e in events)
    report = {
        "version": "1.0",
        "methodology": {
            "purpose": "robustness validation before paper trading",
            "return_proxy": "directional abnormal return from event close",
            "friction_bps": DEFAULT_COST_BPS,
            "slippage_bps": DEFAULT_SLIPPAGE_BPS,
            "min_segment_n": MIN_SEGMENT_N,
            "warning": "abnormal-return proxy; not a fill-level executable backtest",
        },
        "sample": {
            "events": len(events),
            "unique_tickers": len(ticker_counts),
            "top_5": dict(ticker_counts.most_common(5)),
            "top_5_share": sum(n for _, n in ticker_counts.most_common(5)) / len(events) if events else None,
        },
        "overall": _segment_report(events),
        "by_subtype": {},
        "by_source": {},
        "by_direction": {},
        "leave_one_ticker_out": {w: _leave_one_ticker_out(events, w) for w in WINDOWS},
        "qualifying_segments": _qualifying_segments(events),
    }
    for field, target in (("subtype", "by_subtype"), ("source", "by_source"), ("direction", "by_direction")):
        values = sorted({str(e.get(field) or "UNKNOWN").upper() for e in events})
        for value in values:
            report[target][value] = _segment_report(_segment(events, field, value))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    report = build()
    print("========== ROBUST HISTORICAL BACKTEST ==========")
    print(f"Events: {report['sample']['events']}")
    for window, stats in report["overall"].items():
        print(f"{window}: n={stats.get('n', 0)} median={stats.get('median_net_return_pct')}% win={stats.get('win_rate')} PF={stats.get('profit_factor')} DD={stats.get('max_drawdown_pct')}%")
    print(f"Qualifying segments (n>={MIN_SEGMENT_N}, median>=1%, win>=55%): {len(report['qualifying_segments'])}")
    print("Top ticker concentration:", report["sample"]["top_5_share"])
    print("================================================")
    if not report["overall"].get("1D", {}).get("n"):
        raise SystemExit("No usable historical 1D market metrics")


if __name__ == "__main__":
    main()
