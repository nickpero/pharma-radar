from scanner.trial_scanner import deduplicate_alerts


def _alert(title, priority=100, setup=60, reaction=None):
    return {
        "ticker": "SMMT",
        "program": "ivonescimab",
        "subtype": "FDA_APPROVAL",
        "event_timestamp": "2026-09-08T05:00:00+00:00",
        "title": title,
        "alert_priority": priority,
        "trading_setup_score": setup,
        "market_reaction": reaction or {},
        "event": {"type": "FDA_EVENT", "subtype": "FDA_APPROVAL", "title": title},
    }


def test_duplicate_same_event_is_collapsed():
    alerts = deduplicate_alerts([
        _alert("SEC 8-K — Summit Therapeutics (SMMT)"),
        _alert("SEC 8-K — Summit Therapeutics (SMMT)"),
    ])
    assert len(alerts) == 1


def test_same_subtype_different_timestamp_is_kept():
    first = _alert("Summit approval")
    second = _alert("Summit approval")
    second["event_timestamp"] = "2026-09-08T06:00:00+00:00"
    assert len(deduplicate_alerts([first, second])) == 2


def test_richer_duplicate_wins():
    plain = _alert("Summit approval", setup=50)
    rich = _alert("Summit approval", setup=70, reaction={"reaction_5m_pct": 4.2})
    selected = deduplicate_alerts([plain, rich])
    assert len(selected) == 1
    assert selected[0]["trading_setup_score"] == 70


if __name__ == "__main__":
    test_duplicate_same_event_is_collapsed()
    test_same_subtype_different_timestamp_is_kept()
    test_richer_duplicate_wins()
    print("✅ Alert dedup tests passed")



def test_same_day_cross_source_reports_collapse_and_keep_primary_source():
    secondary = _alert("Company says FDA approved ivonescimab", priority=100, setup=90)
    secondary.update({
        "source": "EARLY_DISCOVERY",
        "source_type": "SECONDARY_DISCOVERY",
        "event_timestamp": "2026-09-08T05:00:00+00:00",
        "event_date": "2026-09-08",
        "url": "https://news.example/item",
    })
    primary = _alert("Summit 8-K confirms FDA approval", priority=65, setup=55)
    primary.update({
        "source": "SEC",
        "source_type": "PRIMARY_REGULATORY",
        "event_timestamp": "2026-09-08T08:30:00+00:00",
        "event_date": "2026-09-08",
        "url": "https://sec.example/filing",
    })

    selected = deduplicate_alerts([secondary, primary])

    assert len(selected) == 1
    assert selected[0]["source"] == "SEC"
    assert set(selected[0]["corroborating_sources"]) == {"EARLY_DISCOVERY", "SEC"}
    assert set(selected[0]["corroborating_urls"]) == {
        "https://news.example/item", "https://sec.example/filing"
    }


def test_cross_source_reports_on_different_days_are_kept():
    first = _alert("Summit approval")
    first.update({"source": "SEC", "source_type": "PRIMARY_REGULATORY", "event_date": "2026-09-08"})
    second = _alert("Summit approval")
    second.update({
        "source": "FDA", "source_type": "PRIMARY_REGULATORY",
        "event_date": "2026-09-09", "event_timestamp": "2026-09-09T10:00:00+00:00",
    })
    assert len(deduplicate_alerts([first, second])) == 2


def test_same_day_cross_source_reports_for_different_programs_are_kept():
    first = _alert("Summit approval")
    first.update({"source": "SEC", "source_type": "PRIMARY_REGULATORY", "event_date": "2026-09-08"})
    second = _alert("Summit approval")
    second.update({"source": "FDA", "source_type": "PRIMARY_REGULATORY", "event_date": "2026-09-08"})
    second["program"] = "different-drug"
    assert len(deduplicate_alerts([first, second])) == 2
