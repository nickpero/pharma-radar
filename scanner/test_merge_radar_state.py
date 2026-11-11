from scanner.merge_radar_state import merge_memory


def test_merge_memory_unions_records_and_keeps_earliest_first_seen():
    local = {
        "same": {
            "memory_key": "same",
            "ticker": "ABC",
            "recorded_at": "2026-11-11T10:00:00+00:00",
            "first_seen_at": "2026-11-11T09:00:00+00:00",
            "score": 70,
            "program": "Drug A",
        },
        "local-only": {
            "memory_key": "local-only",
            "recorded_at": "2026-11-11T10:01:00+00:00",
            "ticker": "LOC",
        },
    }
    remote = {
        "same": {
            "memory_key": "same",
            "ticker": "ABC",
            "recorded_at": "2026-11-11T10:05:00+00:00",
            "first_seen_at": "2026-11-11T09:05:00+00:00",
            "score": 85,
            "program": None,
        },
        "remote-only": {
            "memory_key": "remote-only",
            "recorded_at": "2026-11-11T10:02:00+00:00",
            "ticker": "REM",
        },
    }

    merged = merge_memory(local, remote)

    assert set(merged) == {"same", "local-only", "remote-only"}
    assert merged["same"]["score"] == 85
    assert merged["same"]["program"] == "Drug A"
    assert merged["same"]["first_seen_at"] == "2026-11-11T09:00:00+00:00"


def test_merge_memory_handles_empty_sides():
    assert merge_memory({}, {}) == {}
    assert merge_memory({"one": {"ticker": "ABC"}}, {})["one"]["ticker"] == "ABC"
