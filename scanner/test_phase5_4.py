from pathlib import Path
import tempfile

from scanner.catalyst_memory import find_similar_events, load_memory, memory_summary, record_events


def test_memory_upsert_and_summary():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "history.json"
        event = {
            "ticker": "NUVL", "program": "zidesamtinib", "subtype": "FDA_APPROVAL",
            "score": 100, "trading_setup_score": 82, "reaction_strength": "POSITIVE",
            "reaction_interpretation": "CONFIRMED", "event_timestamp": "2026-09-07T14:00:00Z",
        }
        assert record_events([event], path) == 1
        assert record_events([event], path) == 0
        assert len(load_memory(path)) == 1
        assert memory_summary(path) == {"records": 1, "tickers": 1, "catalysts": 1}


def test_similar_events_same_ticker_and_subtype():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "history.json"
        prior = {
            "ticker": "ARGX", "program": "VYVGART", "subtype": "FDA_APPROVAL",
            "event_timestamp": "2026-08-01T14:00:00Z", "score": 100,
        }
        current = {
            "ticker": "ARGX", "program": "VYVGART", "subtype": "FDA_APPROVAL",
            "event_timestamp": "2026-09-07T14:00:00Z", "score": 100,
        }
        record_events([prior], path)
        rows = find_similar_events(current, path=path)
        assert len(rows) == 1
        assert rows[0]["ticker"] == "ARGX"


def test_missing_memory_is_safe():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "missing.json"
        assert load_memory(path) == {}
        assert find_similar_events({"ticker": "NUVL"}, path=path) == []


if __name__ == "__main__":
    test_memory_upsert_and_summary()
    test_similar_events_same_ticker_and_subtype()
    test_missing_memory_is_safe()
    print("Phase 5.4 memory tests passed")
