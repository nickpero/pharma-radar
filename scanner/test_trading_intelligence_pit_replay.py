"""Tests for the point-in-time Trading Intelligence replay."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import scanner.trading_intelligence_pit_replay as mod


def _event(ts, value):
    return {
        "event_timestamp": ts,
        "ticker": "TEST",
        "subtype": "LABEL_EXPANSION",
        "market_metrics": {
            "windows": {"1D": {"directional_abnormal_return_pct": value}}
        },
    }


def test_lookahead_is_excluded():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mod.INPUT = root / "dataset.json"
        mod.OUTPUT = root / "replay.json"
        events = []
        for i in range(30):
            events.append(_event(f"2020-01-{i+1:02d}T10:00:00+00:00", 1.5))
        events.append(_event("2020-02-01T10:00:00+00:00", -5.0))
        mod.INPUT.write_text(json.dumps({"tradable_catalysts": events}), encoding="utf-8")
        report = mod.build()
        assert report["sample"]["events"] == 31
        assert report["sample"]["qualified_historical_edge_events"] == 1
        assert report["events"][29]["prior_subtype_sample"] == 29
        assert report["events"][29]["historical_edge_gate"] is False
        assert report["events"][30]["prior_subtype_sample"] == 30
        assert report["events"][30]["historical_edge_gate"] is True


def test_missing_metrics_are_excluded():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mod.INPUT = root / "dataset.json"
        mod.OUTPUT = root / "replay.json"
        mod.INPUT.write_text(
            json.dumps(
                {
                    "tradable_catalysts": [
                        {"event_timestamp": "2020-01-01T00:00:00Z", "subtype": "FDA_APPROVAL"},
                        _event("2020-01-02T00:00:00Z", 2.0),
                    ]
                }
            ),
            encoding="utf-8",
        )
        report = mod.build()
        assert report["sample"]["events"] == 1

def test_equal_timestamp_events_cannot_qualify_each_other():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mod.INPUT = root / "dataset.json"
        mod.OUTPUT = root / "replay.json"
        events = []
        for i in range(30):
            events.append(_event(f"2020-01-{i+1:02d}T10:00:00+00:00", 1.5))
        events.append(_event("2020-02-01T10:00:00+00:00", 1.5))
        events.append(_event("2020-02-01T10:00:00+00:00", 1.5))
        mod.INPUT.write_text(json.dumps({"tradable_catalysts": events}), encoding="utf-8")
        report = mod.build()
        assert report["events"][30]["historical_edge_gate"] is True
        assert report["events"][31]["historical_edge_gate"] is True
