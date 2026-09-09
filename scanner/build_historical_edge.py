"""Batch builder for the persistent Historical Edge dataset.

Run this as a separate historical job, not on every 15-minute radar scan.
It reads the catalyst memory accumulated by Pharma Radar, fetches daily market
bars, calculates benchmark-adjusted reactions, and writes a compact JSON
artifact that production alerts can consume later.
"""

from __future__ import annotations

import json
from pathlib import Path

from scanner.catalyst_memory import history_records
from scanner.historical_edge import aggregate_historical_edge, calculate_event_metrics
from scanner.historical_market_data import YahooDailyProvider


OUTPUT_FILE = Path("data/historical_edge.json")
BENCHMARK = "XBI"


def build(output_path: Path = OUTPUT_FILE, benchmark: str = BENCHMARK) -> dict:
    events = history_records()
    provider = YahooDailyProvider()
    metrics = []
    failures = []

    for event in events:
        try:
            bars = provider.get_event_bars(event)
            benchmark_bars = provider.get_benchmark_bars(event, benchmark)
            metric = calculate_event_metrics(event, bars, benchmark_bars)
            if metric.get("event_price") is None:
                failures.append({"event_id": metric.get("event_id"), "reason": "missing_event_price"})
                continue
            metrics.append(metric)
        except Exception as error:
            failures.append({"event_id": event.get("memory_key"), "ticker": event.get("ticker"), "reason": str(error)})

    payload = {
        "version": "1.0",
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
    print(f"Events in memory: {payload['events_processed']}")
    print(f"Events with metrics: {payload['events_with_metrics']}")
    print(f"Failures: {payload['failures']}")
    print(f"Benchmark: {payload['benchmark']}")
    print(f"Output: {OUTPUT_FILE}")
    print("======================================")


if __name__ == "__main__":
    main()
