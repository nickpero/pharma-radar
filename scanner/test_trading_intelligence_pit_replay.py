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


def test_warmup_policy_has_explicit_progressive_thresholds():
    assert mod.warmup_policy(0)["stage"] == "WARMUP"
    assert mod.warmup_policy(9)["stage"] == "WARMUP"
    assert mod.warmup_policy(10) == {
        "stage": "PROVISIONAL",
        "min_sample": 10,
        "max_sample": 19,
        "median": 2.00,
        "win_rate": 0.65,
    }
    assert mod.warmup_policy(20) == {
        "stage": "DEVELOPING",
        "min_sample": 20,
        "max_sample": 29,
        "median": 1.50,
        "win_rate": 0.60,
    }
    assert mod.warmup_policy(30) == {
        "stage": "FULL",
        "min_sample": 30,
        "max_sample": None,
        "median": 1.00,
        "win_rate": 0.55,
    }


def test_progressive_warmup_can_qualify_before_full_sample():
    # Raw +2.5% becomes +2.2% after 30 bps friction, so the N=10
    # PROVISIONAL threshold is met with 100% prior wins.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mod.INPUT = root / "dataset.json"
        mod.OUTPUT = root / "replay.json"
        events = [
            _event(f"2020-01-{i+1:02d}T10:00:00+00:00", 2.5)
            for i in range(10)
        ]
        events.append(_event("2020-02-01T10:00:00+00:00", -5.0))
        mod.INPUT.write_text(
            json.dumps({"tradable_catalysts": events}), encoding="utf-8"
        )
        report = mod.build()
        assert report["sample"]["qualified_historical_edge_events"] == 1
        row = report["events"][10]
        assert row["prior_subtype_sample"] == 10
        assert row["warmup_stage"] == "PROVISIONAL"
        assert row["historical_edge_gate"] is True


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
        assert report["events"][30]["warmup_stage"] == "FULL"
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
        assert report["events"][30]["prior_subtype_sample"] == 30
        assert report["events"][31]["prior_subtype_sample"] == 30


def test_portfolio_stats_and_leave_one_ticker_out():
    rows = [
        {"ticker": "A", "forward_1d_net_pct": 2.0},
        {"ticker": "A", "forward_1d_net_pct": -1.0},
        {"ticker": "B", "forward_1d_net_pct": 3.0},
    ]
    stats = mod._portfolio_stats(rows, "1d")
    assert stats["n"] == 3
    assert stats["profit_factor"] == 5.0
    assert stats["win_rate"] == 2 / 3
    loo = mod._loo(rows, "1d")
    assert loo["tickers"] == 2
    assert loo["all_leave_one_ticker_out_positive_median"] is True
