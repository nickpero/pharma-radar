from scripts.update_sec_cik_map import build_watchlist_cik_map, parse_sec_ticker_payload


def test_parse_exchange_map_schema_and_normalize_cik():
    payload = {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [
            [1234, "Example Therapeutics", "EXMP", "Nasdaq"],
            [42, "Another Bio", "BIO", "NYSE"],
        ],
    }
    assert parse_sec_ticker_payload(payload) == {
        "EXMP": "0000001234",
        "BIO": "0000000042",
    }


def test_parse_legacy_sec_ticker_schema():
    payload = {
        "0": {"cik_str": 1234, "ticker": "EXMP", "title": "Example Therapeutics"},
        "1": {"cik_str": 42, "ticker": "BIO", "title": "Another Bio"},
    }
    assert parse_sec_ticker_payload(payload) == {
        "EXMP": "0000001234",
        "BIO": "0000000042",
    }


def test_watchlist_map_prefers_protected_then_official_then_existing():
    watchlist = {"MANUAL": {}, "OFFICIAL": {}, "FALLBACK": {}, "MISSING": {}}
    official = {"MANUAL": "0000000002", "OFFICIAL": "0000000003"}
    existing = {"MANUAL": "0000000001", "FALLBACK": "0000000004"}
    protected = {"MANUAL": "0000000001"}
    result, counts = build_watchlist_cik_map(watchlist, official, existing, protected)

    assert result == {
        "FALLBACK": "0000000004",
        "MANUAL": "0000000001",
        "OFFICIAL": "0000000003",
    }
    assert counts == {
        "protected": 1,
        "official": 1,
        "fallback": 1,
        "unmapped": 1,
    }


def test_watchlist_map_ignores_tickers_not_in_watchlist():
    result, counts = build_watchlist_cik_map(
        {"EXMP": {}},
        {"EXMP": "1234", "UNUSED": "5678"},
    )
    assert result == {"EXMP": "0000001234"}
    assert "UNUSED" not in result
    assert counts["official"] == 1


def test_watchlist_map_respects_explicit_sec_exclusions():
    result, counts = build_watchlist_cik_map(
        {
            "ENABLED": {"company": "Enabled Bio"},
            "DISABLED": {"company": "Disabled Bio", "sec_monitoring": False},
        },
        {"ENABLED": "1234", "DISABLED": "5678"},
    )
    assert result == {"ENABLED": "0000001234"}
    assert counts == {
        "protected": 0,
        "official": 1,
        "fallback": 0,
        "unmapped": 0,
        "excluded": 1,
    }
