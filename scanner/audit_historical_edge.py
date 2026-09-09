"""Audit the historical catalyst dataset before using it for trading intelligence.

This is intentionally read-only: it reports composition, data coverage, direction
bias, and suspicious milestone classifications without changing the dataset.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DATASET = Path("data/historical_edge.json")
DISCOVERY = Path("data/historical_discovered_events.json")

MILESTONES = {
    "TRIAL_STARTED",
    "PRIMARY_COMPLETION",
    "TRIAL_COMPLETED",
    "TRIAL_UPDATED",
    "PHASE_MILESTONE",
}


def main() -> None:
    data = json.loads(DATASET.read_text())
    discovery = json.loads(DISCOVERY.read_text()) if DISCOVERY.exists() else {}
    events = data.get("events") or []

    subtype = Counter(str(e.get("subtype") or "UNKNOWN") for e in events)
    direction = Counter(str(e.get("direction") or "UNKNOWN").upper() for e in events)
    ticker = Counter(str(e.get("ticker") or "UNKNOWN") for e in events)
    source = Counter(str(e.get("source_type") or e.get("source") or "UNKNOWN") for e in events)

    metric_windows = Counter()
    metric_complete = 0
    volume_available = 0
    suspicious_positive_milestones = 0
    failures = data.get("failures", 0)

    for event in events:
        windows = event.get("windows") or {}
        present = sum(
            1
            for window in ("1D", "3D", "5D")
            if (windows.get(window) or {}).get("abnormal_return_pct") is not None
        )
        metric_windows[present] += 1
        if present == 3:
            metric_complete += 1
        if event.get("volume_expansion") is not None:
            volume_available += 1
        if event.get("subtype") in MILESTONES and str(event.get("direction") or "").upper() == "POSITIVE":
            suspicious_positive_milestones += 1

    print("========== HISTORICAL EDGE AUDIT ==========")
    print(f"Discovery events: {discovery.get('events_count', 'n/a')}")
    print(f"Edge events: {len(events)}")
    print(f"Events with any market metric: {len(events) - metric_windows[0]}")
    print(f"Events with complete 1D/3D/5D metrics: {metric_complete}")
    print(f"Events with volume expansion: {volume_available}")
    print(f"Recorded failures: {failures}")
    print()

    print("-- SOURCE --")
    for key, value in source.most_common():
        print(f"{key}: {value}")
    print()

    print("-- SUBTYPE --")
    for key, value in subtype.most_common():
        print(f"{key}: {value}")
    print()

    print("-- DIRECTION --")
    for key, value in direction.most_common():
        print(f"{key}: {value}")
    print()

    print("-- TOP TICKERS --")
    for key, value in ticker.most_common(15):
        print(f"{key}: {value}")
    print()

    print("-- METRIC COVERAGE --")
    for present in (0, 1, 2, 3):
        print(f"{present}/3 windows: {metric_windows[present]}")
    print()

    print("-- METHODOLOGY FLAGS --")
    print(f"Positive-coded generic trial milestones: {suspicious_positive_milestones}")
    if suspicious_positive_milestones:
        print("ACTION: recode generic milestones as NEUTRAL unless outcome evidence supports direction.")
    if source and len(source) == 1 and "CLINICALTRIALS_GOV" in source:
        print("ACTION: historical sample is currently single-source; do not call it multi-source validated.")
    print("===========================================")


if __name__ == "__main__":
    main()
