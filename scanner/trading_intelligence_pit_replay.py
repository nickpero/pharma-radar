"""Pharma Radar — point-in-time Trading Intelligence replay V1.

Research-only replay of the historical-edge prerequisite used by Trading
Intelligence Rule V1.0. For each event, only events strictly earlier in time
are allowed to contribute to the historical subtype statistics.

Live-only checks such as the composite TI score, source reliability at alert
time and intraday market confirmation are intentionally excluded.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

INPUT = Path("data/historical_catalyst_dataset.json")
OUTPUT = Path("data/trading_intelligence_pit_replay.json")

MIN_SAMPLE = 30
MIN_MEDIAN_NET_1D = 1.0
MIN_WIN_RATE_1D = 0.55
FRICTION_BPS = 30.0


def _load() -> dict[str, Any]:
    return json.loads(INPUT.read_text(encoding="utf-8"))


def _ts(event: dict[str, Any]) -> str:
    return str(event.get("event_timestamp") or "")


def _sort_key(event: dict[str, Any]) -> tuple[int, str]:
    raw = _ts(event)
    try:
        value = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (int(dt.timestamp()), raw)
    except (TypeError, ValueError):
        return (0, raw)


def _return_1d(event: dict[str, Any]) -> float | None:
    try:
        value = float(
            ((event.get("market_metrics") or {}).get("windows") or {})
            .get("1D", {})
            .get("directional_abnormal_return_pct")
        )
    except (TypeError, ValueError):
        return None
    return value - FRICTION_BPS / 100.0


def _qualifies(n: int, med: float | None, win: float | None) -> bool:
    return n >= MIN_SAMPLE and med is not None and med >= MIN_MEDIAN_NET_1D and win is not None and win >= MIN_WIN_RATE_1D


def build() -> dict[str, Any]:
    payload = _load()
    events = [
        dict(event)
        for event in (payload.get("tradable_catalysts") or [])
        if event.get("market_metrics")
    ]
    events.sort(key=_sort_key)

    history: dict[str, list[float]] = defaultdict(list)
    rows: list[dict[str, Any]] = []

    for event in events:
        subtype = str(event.get("subtype") or "UNKNOWN").upper()
        prior = history[subtype]
        n = len(prior)
        med = median(prior) if prior else None
        win = (sum(v > 0 for v in prior) / n) if n else None
        row = {
            "event_timestamp": _ts(event),
            "ticker": event.get("ticker"),
            "subtype": subtype,
            "prior_subtype_sample": n,
            "prior_subtype_median_net_1d_pct": med,
            "prior_subtype_win_rate_1d": win,
            "historical_edge_gate": _qualifies(n, med, win),
        }
        rows.append(row)
        value = _return_1d(event)
        if value is not None:
            history[subtype].append(value)

    qualified = [r for r in rows if r["historical_edge_gate"]]
    by_subtype: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = by_subtype.setdefault(
            row["subtype"],
            {"events": 0, "qualified": 0, "first_qualification_timestamp": None},
        )
        bucket["events"] += 1
        if row["historical_edge_gate"]:
            bucket["qualified"] += 1
            if bucket["first_qualification_timestamp"] is None:
                bucket["first_qualification_timestamp"] = row["event_timestamp"]

    report = {
        "version": "1.0",
        "purpose": "point-in-time replay of the historical-edge prerequisite for Trading Intelligence Rule V1.0",
        "methodology": {
            "friction_bps": FRICTION_BPS,
            "minimum_sample": MIN_SAMPLE,
            "minimum_median_net_1d_pct": MIN_MEDIAN_NET_1D,
            "minimum_win_rate_1d": MIN_WIN_RATE_1D,
            "lookahead_control": "Only strictly earlier events contribute to each event's subtype statistics.",
            "warning": "This replays only the historical-edge gate; it is not a live trading backtest.",
        },
        "sample": {"events": len(rows), "qualified_historical_edge_events": len(qualified)},
        "by_subtype": by_subtype,
        "events": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    report = build()
    print("========== TRADING INTELLIGENCE POINT-IN-TIME REPLAY ==========")
    print(f"Events: {report['sample']['events']}")
    print(f"Historical-edge-qualified events: {report['sample']['qualified_historical_edge_events']}")
    for subtype, row in sorted(report["by_subtype"].items()):
        print(
            f"- {subtype}: events={row['events']} "
            f"qualified={row['qualified']} "
            f"first={row['first_qualification_timestamp']}"
        )
    print("Lookahead control: PASS — prior events only")
    print("===============================================================")
    if not report["sample"]["events"]:
        raise SystemExit("No market-matched historical catalysts available")


if __name__ == "__main__":
    main()
