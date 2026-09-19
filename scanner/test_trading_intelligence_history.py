"""Tests for the Trading Intelligence historical gate audit."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import scanner.trading_intelligence_history as mod


def test_qualifies():
    assert mod._qualifies({"n": 30, "median_net_return_pct": 1.0, "win_rate": 0.55})
    assert not mod._qualifies({"n": 29, "median_net_return_pct": 5.0, "win_rate": 0.9})
    assert not mod._qualifies({"n": 30, "median_net_return_pct": 0.99, "win_rate": 0.9})
    assert not mod._qualifies({"n": 30, "median_net_return_pct": 2.0, "win_rate": 0.54})


def test_build():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mod.INPUT = root / "robust.json"
        mod.OUTPUT = root / "audit.json"
        mod.INPUT.write_text(
            json.dumps(
                {
                    "sample": {"events": 81, "unique_tickers": 28},
                    "overall": {"1D": {"n": 81, "median_net_return_pct": 0.984, "win_rate": 0.6049}},
                    "by_subtype": {
                        "LABEL_EXPANSION": {
                            "1D": {"n": 30, "median_net_return_pct": 1.0686, "win_rate": 0.6667, "profit_factor": 5.09}
                        },
                        "FDA_APPROVAL": {
                            "1D": {"n": 13, "median_net_return_pct": 1.045, "win_rate": 0.5385, "profit_factor": 2.36}
                        },
                    },
                    "by_source": {
                        "FDA": {
                            "1D": {"n": 43, "median_net_return_pct": 1.0686, "win_rate": 0.6279, "profit_factor": 3.82}
                        },
                        "FDA_CRL": {
                            "1D": {"n": 38, "median_net_return_pct": 0.5637, "win_rate": 0.5789, "profit_factor": 4.23}
                        },
                    },
                    "by_direction": {
                        "POSITIVE": {
                            "1D": {"n": 43, "median_net_return_pct": 1.0686, "win_rate": 0.6279, "profit_factor": 3.82}
                        },
                        "NEGATIVE": {
                            "1D": {"n": 38, "median_net_return_pct": 0.5637, "win_rate": 0.5789, "profit_factor": 4.23}
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        report = mod.build()
        assert report["qualifying_segment_count"] == 3
        values = {(x["field"], x["value"]) for x in report["qualifying_historical_segments"]}
        assert values == {
            ("subtype", "LABEL_EXPANSION"),
            ("source", "FDA"),
            ("direction", "POSITIVE"),
        }
