from scanner.watchlist_quality import validate_watchlist


def test_valid_watchlist_entry_passes():
    assert validate_watchlist({
        "ABC": {
            "company": "ABC Therapeutics",
            "programs": ["drug-1"],
            "priority": "RED",
            "primary_sources": ["SEC", "FDA"],
        }
    }) == []


def test_missing_programs_and_invalid_priority_fail():
    errors = validate_watchlist({
        "ABC": {"company": "ABC Therapeutics", "programs": [], "priority": "HIGH"}
    })
    assert any("programs" in error for error in errors)
    assert any("priority" in error for error in errors)


def test_empty_source_entry_fails():
    errors = validate_watchlist({
        "ABC": {
            "company": "ABC Therapeutics",
            "programs": ["drug-1"],
            "priority": "ORANGE",
            "primary_sources": ["SEC", ""],
        }
    })
    assert any("primary_sources" in error for error in errors)


def test_malformed_ticker_fails():
    errors = validate_watchlist({
        "abc!": {"company": "ABC Therapeutics", "programs": ["drug-1"], "priority": "RED"}
    })
    assert any("invalid ticker" in error for error in errors)
