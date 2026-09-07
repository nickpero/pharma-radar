from pathlib import Path
import tempfile

from scanner.catalyst_memory import record_events
from scanner.historical_stats import calculate_historical_stats, enrich_historical_stats


def _event(ts, pct, interpretation="CONFIRMED"):
    return {
        "ticker": "NUVL", "program": "zidesamtinib", "subtype": "FDA_APPROVAL",
        "event_timestamp": ts,
        "reaction": {"reaction_15m_pct": pct},
        "reaction_interpretation": interpretation,
    }


def test_historical_stats_exclude_future_events():
    current = _event("2026-09-07T14:00:00Z", 0)
    rows = [
        _event("2026-08-01T14:00:00Z", 10),
        _event("2026-08-15T14:00:00Z", -4, "DIVERGENCE"),
        _event("2026-09-08T14:00:00Z", 100),
    ]
    stats = calculate_historical_stats(current, rows)
    assert stats["sample_size"] == 2
    assert stats["reaction_horizons"]["reaction_15m_pct"]["mean_pct"] == 3.0
    assert stats["positive_rate_15m_pct"] == 50.0


def test_confidence_requires_sample():
    current = _event("2026-09-07T14:00:00Z", 0)
    assert calculate_historical_stats(current, [_event("2026-08-01T14:00:00Z", 5)])["confidence"] == "UNKNOWN"
    rows = [_event(f"2026-08-{i:02d}T14:00:00Z", i) for i in (1, 2, 3)]
    assert calculate_historical_stats(current, rows)["confidence"] == "MEDIUM"


def test_enrichment_uses_persistent_memory():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "history.json"
        record_events([_event("2026-08-01T14:00:00Z", 6)], path)
        record_events([_event("2026-08-02T14:00:00Z", 4)], path)
        record_events([_event("2026-08-03T14:00:00Z", -2, "DIVERGENCE")], path)
        current = _event("2026-09-07T14:00:00Z", 0)
        result = enrich_historical_stats(current, path=path)
        assert result["historical_sample_size"] == 3
        assert result["historical_confidence"] == "MEDIUM"
        assert result["historical_stats"]["positive_rate_15m_pct"] == 66.7
        assert result["historical_stats"]["divergence_rate_pct"] == 33.3


if __name__ == "__main__":
    test_historical_stats_exclude_future_events()
    test_confidence_requires_sample()
    test_enrichment_uses_persistent_memory()
    print("Phase 5.5 historical intelligence tests passed")
