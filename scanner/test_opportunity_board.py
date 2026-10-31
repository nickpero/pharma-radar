from datetime import datetime, timedelta, timezone

from scanner.opportunity_board import build_opportunity_board, format_board_summary


def test_board_separates_live_watch_late_and_excluded_events():
    now = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)
    watchlist = {"ABC": {"company": "ABC Pharma", "programs": ["drug-a"]}}
    events = [
        {
            "ticker": "ABC", "company": "ABC Pharma", "program": "drug-a",
            "subtype": "TOPLINE_RESULTS", "source": "SEC", "source_type": "PRIMARY_CORPORATE",
            "published_at": (now - timedelta(hours=2)).isoformat(),
            "score": 95, "alert_priority": 90, "volume_ratio": 3.2,
            "price_change_pct": 8.5, "url": "https://example.com/abc",
        },
        {
            "ticker": "ABC", "program": "drug-a", "subtype": "CLINICAL_RESULTS",
            "source": "FDA", "source_type": "PRIMARY_REGULATORY",
            "event_timestamp": "2026-10-31", "score": 80,
        },
        {
            "ticker": "ABC", "program": "drug-a", "subtype": "CLINICAL_RESULTS",
            "source": "SEC", "source_type": "PRIMARY_CORPORATE",
            "event_timestamp": (now - timedelta(hours=36)).isoformat(),
        },
        {
            "ticker": "ABC", "program": "drug-a", "subtype": "CLINICAL_RESULTS",
            "source": "SEC", "source_type": "PRIMARY_CORPORATE",
            "event_timestamp": (now - timedelta(days=5)).isoformat(),
        },
        {
            "ticker": "ABC", "program": "drug-a", "subtype": "CLINICAL_RESULTS",
            "source": "BLOG", "source_type": "SECONDARY",
            "published_at": (now - timedelta(hours=1)).isoformat(),
        },
    ]

    board = build_opportunity_board(
        events=events, watchlist=watchlist, upcoming=[], now=now,
    )

    assert len(board["live"]) == 1
    assert board["live"][0]["ticker"] == "ABC"
    assert board["live"][0]["market"]["volume_ratio"] == 3.2
    assert board["live"][0]["market"]["market_cap"] is None
    assert len(board["watch"]) == 1
    assert board["watch"][0]["reason"] == "DATE_PRECISION_INSUFFICIENT"
    assert len(board["late"]) == 2
    assert len(board["excluded"]) == 1
    assert board["counts"]["upcoming"] == 0


def test_fresh_event_with_unverified_program_is_watch_not_live():
    now = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)
    event = {
        "ticker": "ABC", "program": "unknown-drug", "subtype": "TOPLINE_RESULTS",
        "source": "SEC", "source_type": "PRIMARY_CORPORATE",
        "published_at": (now - timedelta(hours=1)).isoformat(),
    }
    board = build_opportunity_board(
        events=[event],
        watchlist={"ABC": {"company": "ABC", "programs": ["drug-a"]}},
        upcoming=[], now=now,
    )
    assert board["live"] == []
    assert board["watch"][0]["program_status"] == "PROGRAM_MISMATCH"


def test_missing_or_timezone_ambiguous_publication_time_is_not_live():
    now = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)
    events = [
        {"ticker": "ABC", "program": "drug-a", "source": "SEC", "source_type": "PRIMARY_CORPORATE"},
        {"ticker": "ABC", "program": "drug-a", "source": "SEC", "source_type": "PRIMARY_CORPORATE",
         "published_at": "2026-10-31T09:00:00"},
    ]
    board = build_opportunity_board(
        events=events,
        watchlist={"ABC": {"company": "ABC", "programs": ["drug-a"]}},
        upcoming=[], now=now,
    )
    assert board["live"] == []
    assert len(board["excluded"]) == 2


def test_upcoming_milestones_are_kept_separate_and_labelled_as_estimates():
    upcoming = [{
        "ticker": "ABC", "milestone": "PRIMARY_COMPLETION",
        "date": "2026-11-20", "date_precision": "DAY",
        "date_is_estimate": True, "clinical_outcome_available": False,
    }]
    board = build_opportunity_board(
        events=[], watchlist={}, upcoming=upcoming,
        now=datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc),
    )
    assert board["upcoming"][0]["date_is_estimate"] is True
    assert board["counts"]["upcoming"] == 1
    summary = format_board_summary(board)
    assert "LIVE=0" in summary
    assert "UPCOMING=1" in summary


def test_catalyst_memory_preserves_first_seen_time_across_repeated_scans(tmp_path):
    from scanner.catalyst_memory import history_records, record_events

    path = tmp_path / "catalyst_history.json"
    original = {
        "ticker": "ABC", "program": "drug-a", "subtype": "TOPLINE_RESULTS",
        "source": "SEC", "source_type": "PRIMARY_CORPORATE",
        "event_timestamp": "2026-10-31T08:00:00+00:00",
        "first_seen_at": "2026-10-31T08:02:00+00:00",
    }
    record_events([original], path=path)
    repeated = dict(original, first_seen_at="2026-10-31T08:12:00+00:00")
    record_events([repeated], path=path)

    rows = history_records(path=path)
    assert len(rows) == 1
    assert rows[0]["first_seen_at"] == "2026-10-31T08:02:00+00:00"
