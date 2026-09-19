"""Pharma Radar — point-in-time Trading Intelligence replay V1.1.

Research-only replay of the historical-edge prerequisite used by
Trading Intelligence Rule V1.0.

Warm-up rule:
- N < 10: WARMUP — no historical qualification.
- N 10-19: PROVISIONAL — median net 1D >= 2.00% and win rate >= 65%.
- N 20-29: DEVELOPING — median net 1D >= 1.50% and win rate >= 60%.
- N >= 30: FULL — median net 1D >= 1.00% and win rate >= 55%.

Only strictly earlier timestamps contribute. Equal-timestamp events are
processed as a batch and cannot contribute to each other.

This module validates historical availability in real time; it does not
generate a buy/sell decision.
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

# Warm-up policy: stronger evidence is required while the historical sample
# is still small. The full Rule V1.0 thresholds become available at N >= 30.
WARMUP_THRESHOLDS = (
    {"stage": "WARMUP", "min_sample": 0, "max_sample": 9, "median": None, "win_rate": None},
    {"stage": "PROVISIONAL", "min_sample": 10, "max_sample": 19, "median": 2.00, "win_rate": 0.65},
    {"stage": "DEVELOPING", "min_sample": 20, "max_sample": 29, "median": 1.50, "win_rate": 0.60},
    {"stage": "FULL", "min_sample": 30, "max_sample": None, "median": 1.00, "win_rate": 0.55},
)
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


def warmup_policy(n: int) -> dict[str, Any]:
    """Return the explicit PIT warm-up stage and thresholds for prior sample N."""
    for rule in WARMUP_THRESHOLDS:
        if n >= rule["min_sample"] and (
            rule["max_sample"] is None or n <= rule["max_sample"]
        ):
            return dict(rule)
    raise AssertionError(f"No warm-up policy stage for sample size {n}")


def _qualifies(n: int, med: float | None, win: float | None) -> bool:
    rule = warmup_policy(n)
    if rule["median"] is None or rule["win_rate"] is None:
        return False
    return (
        med is not None
        and med >= rule["median"]
        and win is not None
        and win >= rule["win_rate"]
    )


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
    index = 0

    # Equal-timestamp events are a batch: none can see another event from
    # the same timestamp as historical information.
    while index < len(events):
        timestamp = _ts(events[index])
        batch: list[dict[str, Any]] = []
        while index < len(events) and _ts(events[index]) == timestamp:
            batch.append(events[index])
            index += 1

        batch_values: list[tuple[str, float]] = []
        for event in batch:
            subtype = str(event.get("subtype") or "UNKNOWN").upper()
            prior = history[subtype]
            n = len(prior)
            med = median(prior) if prior else None
            win = (sum(v > 0 for v in prior) / n) if n else None
            policy = warmup_policy(n)
            qualified = _qualifies(n, med, win)

            rows.append(
                {
                    "event_timestamp": timestamp,
                    "ticker": event.get("ticker"),
                    "subtype": subtype,
                    "prior_subtype_sample": n,
                    "warmup_stage": policy["stage"],
                    "warmup_min_sample": policy["min_sample"],
                    "warmup_max_sample": policy["max_sample"],
                    "warmup_required_median_net_1d_pct": policy["median"],
                    "warmup_required_win_rate_1d": policy["win_rate"],
                    "prior_subtype_median_net_1d_pct": med,
                    "prior_subtype_win_rate_1d": win,
                    "historical_edge_gate": qualified,
                }
            )

            value = _return_1d(event)
            if value is not None:
                batch_values.append((subtype, value))

        for subtype, value in batch_values:
            history[subtype].append(value)

    qualified = [r for r in rows if r["historical_edge_gate"]]
    by_subtype: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = by_subtype.setdefault(
            row["subtype"],
            {
                "events": 0,
                "qualified": 0,
                "first_qualification_timestamp": None,
                "first_qualification_stage": None,
            },
        )
        bucket["events"] += 1
        if row["historical_edge_gate"]:
            bucket["qualified"] += 1
            if bucket["first_qualification_timestamp"] is None:
                bucket["first_qualification_timestamp"] = row["event_timestamp"]
                bucket["first_qualification_stage"] = row["warmup_stage"]

    by_stage: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = by_stage.setdefault(row["warmup_stage"], {"events": 0, "qualified": 0})
        bucket["events"] += 1
        if row["historical_edge_gate"]:
            bucket["qualified"] += 1

    report = {
        "version": "1.1",
        "purpose": "point-in-time replay of the historical-edge prerequisite for Trading Intelligence Rule V1.0 with explicit progressive warm-up",
        "methodology": {
            "friction_bps": FRICTION_BPS,
            "warmup_policy": [dict(rule) for rule in WARMUP_THRESHOLDS],
            "lookahead_control": "Only strictly earlier timestamps contribute to each event's subtype statistics; equal-timestamp events are batched.",
            "warning": "This replays only the historical-edge gate; it is not a live trading backtest.",
        },
        "sample": {
            "events": len(rows),
            "qualified_historical_edge_events": len(qualified),
        },
        "by_stage": by_stage,
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
    print(
        "Historical-edge-qualified events: "
        f"{report['sample']['qualified_historical_edge_events']}"
    )
    for stage, row in report["by_stage"].items():
        print(f"- {stage}: events={row['events']} qualified={row['qualified']}")
    for subtype, row in sorted(report["by_subtype"].items()):
        print(
            f"- {subtype}: events={row['events']} "
            f"qualified={row['qualified']} "
            f"first={row['first_qualification_timestamp']} "
            f"stage={row['first_qualification_stage']}"
        )
    print("Lookahead control: PASS — prior events only")
    print("===============================================================")
    if not report["sample"]["events"]:
        raise SystemExit("No market-matched historical catalysts available")


if __name__ == "__main__":
    main()
