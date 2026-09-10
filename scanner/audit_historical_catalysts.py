"""Audit the clean historical catalyst sample before using it for trading research.

This is a read-only QA layer. It does not generate trade recommendations.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

DATASET = Path("data/historical_catalyst_dataset.json")
OUTPUT = Path("data/historical_catalyst_audit.json")
WINDOWS = ("1D", "3D", "5D")


def _load() -> dict[str, Any]:
    if not DATASET.exists() or DATASET.stat().st_size == 0:
        return {}
    return json.loads(DATASET.read_text(encoding="utf-8"))


def _date_key(value: Any) -> str:
    text = str(value or "")
    if not text:
        return "UNKNOWN"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def _metrics(event: dict[str, Any]) -> dict[str, Any]:
    return event.get("market_metrics") or {}


def audit() -> dict[str, Any]:
    payload = _load()
    events = list(payload.get("tradable_catalysts") or [])

    duplicate_keys: Counter[str] = Counter()
    ticker_counts: Counter[str] = Counter()
    subtype_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    direction_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    directional_signs: dict[str, list[float]] = defaultdict(list)
    window_values: dict[str, list[float]] = defaultdict(list)
    volume_values: list[float] = []
    missing_metrics = 0
    missing_windows = Counter()
    negative_direction_mismatches = 0
    suspicious_generic = 0

    for event in events:
        event_id = str(event.get("event_id") or "|".join(str(event.get(k) or "") for k in ("ticker", "program", "subtype", "event_timestamp", "source")))
        duplicate_keys[event_id] += 1
        ticker = str(event.get("ticker") or "UNKNOWN")
        subtype = str(event.get("subtype") or "UNKNOWN")
        source = str(event.get("source") or "UNKNOWN")
        direction = str(event.get("direction") or "UNKNOWN").upper()
        ticker_counts[ticker] += 1
        subtype_counts[subtype] += 1
        source_counts[source] += 1
        direction_counts[direction] += 1
        year_counts[_date_key(event.get("event_timestamp"))[:4]] += 1

        metrics = _metrics(event)
        if not metrics:
            missing_metrics += 1
            continue
        volume = metrics.get("volume_expansion")
        if volume is not None:
            try:
                volume_values.append(float(volume))
            except (TypeError, ValueError):
                pass

        for window in WINDOWS:
            row = (metrics.get("windows") or {}).get(window) or {}
            value = row.get("directional_abnormal_return_pct")
            if value is None:
                missing_windows[window] += 1
            else:
                try:
                    numeric = float(value)
                    directional_signs[window].append(numeric)
                    window_values[window].append(numeric)
                except (TypeError, ValueError):
                    missing_windows[window] += 1

        # A negative event should only count as directionally successful when
        # the raw abnormal return is negative. The engine stores the inverted
        # directional value, so a negative raw return should become positive.
        if direction == "NEGATIVE":
            for window in WINDOWS:
                row = (metrics.get("windows") or {}).get(window) or {}
                raw = row.get("abnormal_return_pct")
                oriented = row.get("directional_abnormal_return_pct")
                if raw is not None and oriented is not None:
                    try:
                        if float(raw) < 0 and float(oriented) <= 0:
                            negative_direction_mismatches += 1
                        if float(raw) > 0 and float(oriented) >= 0:
                            negative_direction_mismatches += 1
                    except (TypeError, ValueError):
                        pass

        text = " ".join(str(event.get(k) or "") for k in ("program", "company", "subtype")).lower()
        if subtype in {"TRIAL_STARTED", "TRIAL_UPDATED", "TRIAL_COMPLETED", "PRIMARY_COMPLETION", "PHASE_MILESTONE"}:
            suspicious_generic += 1
        if any(token in text for token in ("unknown", "n/a", "none")):
            suspicious_generic += 1

    duplicates = {key: count for key, count in duplicate_keys.items() if count > 1}

    per_ticker: dict[str, Any] = {}
    for ticker, count in ticker_counts.items():
        subset = [e for e in events if str(e.get("ticker") or "UNKNOWN") == ticker]
        per_ticker[ticker] = {
            "events": count,
            "subtypes": dict(Counter(str(e.get("subtype") or "UNKNOWN") for e in subset)),
            "directions": dict(Counter(str(e.get("direction") or "UNKNOWN").upper() for e in subset)),
        }

    summary = {
        "events": len(events),
        "events_with_market_metrics": len(events) - missing_metrics,
        "missing_market_metrics": missing_metrics,
        "duplicates": len(duplicates),
        "duplicate_event_rows": sum(duplicates.values()) - len(duplicates),
        "missing_windows": dict(missing_windows),
        "direction_mismatches": negative_direction_mismatches,
        "median_directional_abnormal_return": {
            window: (median(values) if values else None) for window, values in window_values.items()
        },
        "win_rate_directional": {
            window: (sum(value > 0 for value in values) / len(values) if values else None)
            for window, values in window_values.items()
        },
        "median_volume_expansion": median(volume_values) if volume_values else None,
    }

    result = {
        "version": "1.0",
        "summary": summary,
        "by_subtype": dict(subtype_counts),
        "by_source": dict(source_counts),
        "by_direction": dict(direction_counts),
        "by_year": dict(sorted(year_counts.items())),
        "top_tickers": dict(ticker_counts.most_common(20)),
        "per_ticker": per_ticker,
        "duplicates": duplicates,
        "methodology_flags": {
            "generic_trial_milestones_in_tradable_sample": suspicious_generic,
            "negative_direction_mismatches": negative_direction_mismatches,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main() -> None:
    result = audit()
    summary = result["summary"]
    print("========== HISTORICAL CATALYST AUDIT ==========")
    print(f"Tradable catalysts: {summary['events']}")
    print(f"With market metrics: {summary['events_with_market_metrics']}")
    print(f"Missing market metrics: {summary['missing_market_metrics']}")
    print(f"Duplicate keys: {summary['duplicates']}")
    print(f"Duplicate extra rows: {summary['duplicate_event_rows']}")
    print(f"Missing windows: {summary['missing_windows']}")
    print(f"Direction mismatches: {summary['direction_mismatches']}")
    print(f"Median directional abnormal return: {summary['median_directional_abnormal_return']}")
    print(f"Directional win rate: {summary['win_rate_directional']}")
    print(f"Median volume expansion: {summary['median_volume_expansion']}")
    print(f"By subtype: {result['by_subtype']}")
    print(f"By source: {result['by_source']}")
    print(f"By direction: {result['by_direction']}")
    print(f"By year: {result['by_year']}")
    print(f"Top tickers: {result['top_tickers']}")
    print("===============================================")

    if summary["events"] == 0:
        raise SystemExit("No tradable catalysts available for audit")
    if summary["missing_market_metrics"] == summary["events"]:
        raise SystemExit("No tradable catalyst has market metrics")
    if summary["duplicates"]:
        raise SystemExit("Duplicate event keys detected")
    if summary["direction_mismatches"]:
        raise SystemExit("Directional abnormal-return mismatch detected")
    if result["methodology_flags"]["generic_trial_milestones_in_tradable_sample"]:
        raise SystemExit("Generic trial milestones leaked into tradable sample")


if __name__ == "__main__":
    main()
