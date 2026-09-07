"""Tests for the deliberately small Phase 5.7.1 backtest dataset layer."""

from scanner.backtest import build_dataset, summarize_all_horizons, summarize_outcomes


def _row():
    return {
        "memory_key": "abc",
        "ticker": "NUVL",
        "company": "Nuvalent",
        "program": "zidesamtinib",
        "subtype": "FDA_APPROVAL",
        "direction": "POSITIVE",
        "severity": "HIGH",
        "score": 100,
        "alert_priority": 96,
        "event_surprise": "UNEXPECTED",
        "trading_setup_score": 78,
        "reaction_strength": "POSITIVE",
        "reaction_interpretation": "CONFIRMED",
        "price_change_pct": 2.1,
        "volume_ratio": 3.2,
        "market_cap": 500_000_000,
        "short_interest_pct": 8,
        "event_timestamp": "2026-09-01T14:00:00+00:00",
        "reaction": {
            "reaction_1m_pct": 0.8,
            "reaction_5m_pct": 1.5,
            "reaction_15m_pct": 3.0,
            "reaction_30m_pct": 2.5,
            "reaction_60m_pct": -1.0,
        },
    }


def test_build_dataset_preserves_point_in_time_fields_and_fixed_outcomes():
    dataset = build_dataset([_row()])
    assert len(dataset) == 1
    row = dataset[0]
    assert row["ticker"] == "NUVL"
    assert row["score"] == 100
    assert row["alert_priority"] == 96
    assert row["outcomes"]["15m"] == 3.0
    assert row["outcomes_available"] == 5


def test_missing_reaction_is_safe():
    row = _row()
    row.pop("reaction")
    dataset = build_dataset([row])
    assert dataset[0]["outcomes_available"] == 0
    assert summarize_outcomes(dataset, "15m")["observations"] == 0


def test_summary_is_descriptive_not_optimized():
    dataset = build_dataset([_row()])
    summary = summarize_outcomes(dataset, "15m")
    assert summary["observations"] == 1
    assert summary["win_rate"] == 1.0
    assert summary["average_return_pct"] == 3.0
    assert summary["median_return_pct"] == 3.0


def test_all_horizons():
    summaries = summarize_all_horizons(build_dataset([_row()]))
    assert set(summaries) == {"1m", "5m", "15m", "30m", "60m"}
    assert summaries["60m"]["average_return_pct"] == -1.0
