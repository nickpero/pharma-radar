"""Batch builder for the persistent Historical Edge dataset.

The builder combines live catalyst memory with the conservative historical
backfill discovered from primary SEC/FDA sources. Market prices are resolved
from daily bars, so historical event records never need fabricated prices.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scanner.catalyst_memory import history_records
from scanner.historical_edge import aggregate_historical_edge, calculate_event_metrics
from scanner.historical_market_data import YahooDailyProvider


OUTPUT_FILE = Path("data/historical_edge.json")
DISCOVERED_FILE = Path("data/historical_discovered_events.json")
BENCHMARK = "XBI"


def _event_key(event: dict[str, Any]) -> str:
    raw = "|".join(str(event.get(k) or "") for k in ("ticker", "program", "subtype", "event_timestamp", "source", "url"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _load_discovered() -> list[dict[str, Any]]:
    if not DISCOVERED_FILE.exists():
        return []
    try:
        payload = json.loads(DISCOVERED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload.get("events") or [] if isinstance(payload, dict) else []


def _merged_events() -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for event in history_records():
        item = dict(event)
        item["event_id"] = item.get("memory_key") or _event_key(item)
        merged[item["event_id"]] = item
    for event in _load_discovered():
        item = dict(event)
        item["event_id"] = item.get("event_id") or _event_key(item)
        # Live memory wins when the exact same catalyst already exists.
        merged.setdefault(item["event_id"], item)
    return sorted(merged.values(), key=lambda x: str(x.get("event_timestamp") or ""))


def build(output_path: Path = OUTPUT_FILE, benchmark: str = BENCHMARK) -> dict:
    events = _merged_events()
    provider = YahooDailyProvider()
    metrics = []
    failures = []

    for event in events:
        try:
            bars = provider.get_event_bars(event)
            benchmark_bars = provider.get_benchmark_bars(event, benchmark)
            metric = calculate_event_metrics(event, bars, benchmark_bars)
            if metric.get("event_price") is None:
                failures.append({"event_id": metric.get("event_id"), "reason": "missing_event_price", "ticker": event.get("ticker")})
                continue
            metrics.append(metric)
        except Exception as error:
            failures.append({"event_id": event.get("event_id") or event.get("memory_key"), "ticker": event.get("ticker"), "reason": str(error)})

    payload = {
        "version": "1.1",
        "benchmark": benchmark,
        "events_processed": len(events),
        "events_with_metrics": len(metrics),
        "failures": len(failures),
        "events": metrics,
        "by_subtype": aggregate_historical_edge(metrics, "subtype"),
        "by_ticker": aggregate_historical_edge(metrics, "ticker"),
        "by_program": aggregate_historical_edge(metrics, "program"),
        "failed_events": failures[:200],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
    tmp.replace(output_path)
    return payload


def main() -> None:
    payload = build()
    print("========== HISTORICAL EDGE ==========")
    print(f"Events discovered/remembered: {payload['events_processed']}")
    print(f"Events with metrics: {payload['events_with_metrics']}")
    print(f"Failures: {payload['failures']}")
    print(f"Benchmark: {payload['benchmark']}")
    print(f"Output: {OUTPUT_FILE}")
    print("======================================")


if __name__ == "__main__":
    main()
