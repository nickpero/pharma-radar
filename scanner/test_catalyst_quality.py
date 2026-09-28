from datetime import datetime, timezone

from scanner.catalyst_quality import qualify_catalyst


NOW = datetime(2026, 9, 28, 20, 0, tzinfo=timezone.utc)


def test_phase3_primary_is_included():
    event = {
        "subtype": "PRIMARY_ENDPOINT_MET",
        "score": 100,
        "source_type": "PRIMARY_CLINICAL",
        "source": "COMPANY",
        "event_timestamp": "2026-09-28T18:00:00Z",
        "price_change_pct": 120,
        "volume_ratio": 8,
    }
    result = qualify_catalyst(event, now=NOW)
    assert result["catalyst_class"] == "FUNDAMENTAL_CLINICAL"
    assert result["catalyst_primary_source"] is True
    assert result["radar_inclusion"] == "INCLUDE"
    assert result["radar_priority"] == "P0"
    assert result["catalyst_freshness"] == "FRESH"


def test_fda_primary_is_included_without_market_move():
    event = {
        "subtype": "FDA_APPROVAL",
        "score": 100,
        "source_type": "PRIMARY_REGULATORY",
        "source": "FDA",
        "published_at": "2026-09-28T19:30:00Z",
    }
    result = qualify_catalyst(event, now=NOW)
    assert result["catalyst_class"] == "FUNDAMENTAL_REGULATORY"
    assert result["radar_inclusion"] == "INCLUDE"
    assert result["radar_priority"] == "P1"


def test_speculative_move_never_becomes_high_priority():
    event = {
        "subtype": "OTHER",
        "score": 20,
        "source_type": "SECONDARY_NEWS",
        "source": "NEWS",
        "title": "Blockchain momentum and short squeeze",
        "price_change_pct": 60,
        "volume_ratio": 10,
        "published_at": "2026-09-28T18:00:00Z",
    }
    result = qualify_catalyst(event, now=NOW)
    assert result["catalyst_class"] == "SPECULATIVE"
    assert result["radar_priority"] == "P2"
    assert result["radar_inclusion"] == "WATCH"


def test_unexplained_move_is_not_promoted():
    event = {
        "subtype": "OTHER",
        "score": 20,
        "source_type": "SECONDARY_NEWS",
        "source": "NEWS",
        "title": "Unusual volume",
        "price_change_pct": 45,
        "volume_ratio": 6,
        "published_at": "2026-09-28T18:00:00Z",
    }
    result = qualify_catalyst(event, now=NOW)
    assert result["catalyst_class"] == "TECHNICAL"
    assert result["radar_inclusion"] == "WATCH"
    assert result["radar_priority"] == "P2"


def test_corporate_primary_is_separate_class():
    event = {
        "subtype": "PARTNERSHIP",
        "score": 70,
        "source_type": "PRIMARY_CORPORATE",
        "source": "COMPANY",
        "title": "Strategic partnership for pharmaceutical manufacturing",
        "published_at": "2026-09-28T18:30:00Z",
    }
    result = qualify_catalyst(event, now=NOW)
    assert result["catalyst_class"] == "FUNDAMENTAL_CORPORATE"
    assert result["radar_inclusion"] == "INCLUDE"
