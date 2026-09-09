"""Build the clean historical catalyst dataset used for trading analysis."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DISCOVERED = Path("data/historical_discovered_events.json")
EDGE = Path("data/historical_edge.json")
OUTPUT = Path("data/historical_catalyst_dataset.json")

TRADABLE_SUBTYPES = {
    "CLINICAL_RESULTS", "FDA_APPROVAL", "FDA_REJECTION", "FDA_SAFETY_WARNING",
    "TRIAL_HOLD", "TRIAL_HOLD_LIFTED", "PHASE_ADVANCED", "REGULATORY_FILING",
    "LABEL_EXPANSION", "DATE_ACCELERATED", "DATE_DELAYED",
}
INFORMATIONAL_SUBTYPES = {
    "TRIAL_UPDATED", "TRIAL_STARTED", "PRIMARY_COMPLETION", "TRIAL_COMPLETED",
    "TRIAL_RESULTS_POSTED", "PHASE_MILESTONE",
}


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _event_key(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or "|".join(str(event.get(k) or "") for k in (
        "ticker", "program", "subtype", "event_timestamp", "source"
    )))


def build() -> dict[str, Any]:
    discovered = _load(DISCOVERED)
    edge = _load(EDGE)
    metrics = {_event_key(event): event for event in edge.get("events") or []}
    tradable: list[dict[str, Any]] = []
    informational: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for event in discovered.get("events") or []:
        subtype = str(event.get("subtype") or "").upper()
        item = dict(event)
        item["dataset_class"] = "TRADABLE_CATALYST" if subtype in TRADABLE_SUBTYPES else "INFORMATIONAL_MILESTONE"
        metric = metrics.get(_event_key(event))
        if metric:
            item["market_metrics"] = metric
        if subtype in TRADABLE_SUBTYPES:
            tradable.append(item)
        elif subtype in INFORMATIONAL_SUBTYPES:
            informational.append(item)
        else:
            excluded.append(item)

    by_subtype: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_direction: dict[str, int] = {}
    for event in tradable:
        subtype = str(event.get("subtype") or "UNKNOWN")
        source = str(event.get("source") or "UNKNOWN")
        direction = str(event.get("direction") or "UNKNOWN")
        by_subtype[subtype] = by_subtype.get(subtype, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1
        by_direction[direction] = by_direction.get(direction, 0) + 1

    payload = {
        "version": "1.0",
        "tradable_catalysts": tradable,
        "informational_milestones": informational,
        "excluded": excluded,
        "counts": {
            "discovered": len(discovered.get("events") or []),
            "tradable": len(tradable),
            "informational": len(informational),
            "excluded": len(excluded),
            "tradable_with_market_metrics": sum(1 for x in tradable if x.get("market_metrics")),
        },
        "by_subtype": dict(sorted(by_subtype.items())),
        "by_source": dict(sorted(by_source.items())),
        "by_direction": dict(sorted(by_direction.items())),
        "eligible_subtypes": sorted(TRADABLE_SUBTYPES),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    payload = build()
    print("========== HISTORICAL CATALYST DATASET ==========")
    print(f"Discovered: {payload['counts']['discovered']}")
    print(f"Tradable catalysts: {payload['counts']['tradable']}")
    print(f"Informational milestones: {payload['counts']['informational']}")
    print(f"Tradable with market metrics: {payload['counts']['tradable_with_market_metrics']}")
    print(f"By subtype: {payload['by_subtype']}")
    print(f"By source: {payload['by_source']}")
    print(f"By direction: {payload['by_direction']}")
    print("==================================================")


if __name__ == "__main__":
    main()
