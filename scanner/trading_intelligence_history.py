"""Pharma Radar — Trading Intelligence historical gate audit V1.

Research-only audit of the historical evidence used by Trading Intelligence Rule
V1.0. It deliberately separates historical prerequisites from live-only checks
(TI composite score, source reliability at alert time, and intraday reaction).

This module does not produce buy/sell recommendations.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INPUT = Path("data/robust_historical_backtest.json")
OUTPUT = Path("data/trading_intelligence_history_audit.json")

MIN_SAMPLE = 30
MIN_MEDIAN_NET_1D = 1.0
MIN_WIN_RATE_1D = 0.55


def _load() -> dict[str, Any]:
    return json.loads(INPUT.read_text(encoding="utf-8"))


def _qualifies(stats: dict[str, Any]) -> bool:
    return (
        int(stats.get("n", 0)) >= MIN_SAMPLE
        and float(stats.get("median_net_return_pct", -999.0)) >= MIN_MEDIAN_NET_1D
        and float(stats.get("win_rate", 0.0)) >= MIN_WIN_RATE_1D
    )


def _segment_rows(payload: dict[str, Any], section: str) -> list[dict[str, Any]]:
    rows = []
    for value, windows in sorted((payload.get(section) or {}).items()):
        stats = windows.get("1D") or {}
        rows.append(
            {
                "field": section.removeprefix("by_"),
                "value": value,
                "n": int(stats.get("n", 0)),
                "median_net_return_1d_pct": stats.get("median_net_return_pct"),
                "win_rate_1d": stats.get("win_rate"),
                "profit_factor_1d": stats.get("profit_factor"),
                "qualifies_historical_gate": _qualifies(stats),
            }
        )
    return rows


def build() -> dict[str, Any]:
    payload = _load()
    overall = payload.get("overall", {}).get("1D") or {}
    sample = payload.get("sample") or {}
    sections = {
        "subtype": _segment_rows(payload, "by_subtype"),
        "source": _segment_rows(payload, "by_source"),
        "direction": _segment_rows(payload, "by_direction"),
    }
    qualifying = [
        row
        for rows in sections.values()
        for row in rows
        if row["qualifies_historical_gate"]
    ]

    report = {
        "version": "1.0",
        "purpose": "historical evidence audit for Trading Intelligence Rule V1.0",
        "methodology": {
            "historical_gate": {
                "minimum_sample": MIN_SAMPLE,
                "minimum_median_net_1d_pct": MIN_MEDIAN_NET_1D,
                "minimum_win_rate_1d": MIN_WIN_RATE_1D,
                "friction_included_in_input": True,
            },
            "not_tested_historically": [
                "live trading_intelligence_score >= 80",
                "primary/reliable source classification at alert time",
                "2-of-3 live market confirmations",
            ],
            "warning": "Historical segment statistics are descriptive evidence, not a validated live trading strategy.",
        },
        "sample": sample,
        "overall_1d": overall,
        "segments": sections,
        "qualifying_historical_segments": qualifying,
        "qualifying_segment_count": len(qualifying),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    report = build()
    print("========== TRADING INTELLIGENCE HISTORY AUDIT ==========")
    print(f"Events: {report['sample'].get('events', 0)}")
    print(f"Unique tickers: {report['sample'].get('unique_tickers', 0)}")
    print(f"Historical-gate segments: {report['qualifying_segment_count']}")
    for row in report["qualifying_historical_segments"]:
        print(
            f"- {row['field']}={row['value']}: "
            f"n={row['n']} median_1D_net={row['median_net_return_1d_pct']}% "
            f"win={row['win_rate_1d']}"
        )
    print("Live-only checks intentionally not backfilled: TI score, source reliability, market confirmation")
    print("========================================================")
    if not report["overall_1d"]:
        raise SystemExit("Missing robust 1D historical statistics")


if __name__ == "__main__":
    main()
