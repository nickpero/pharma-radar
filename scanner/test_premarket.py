from datetime import datetime, timezone
from unittest.mock import Mock

from scanner.premarket import get_premarket_snapshot, score_opportunity, format_report


def test_no_catalyst_is_not_able_to_fake_a_high_opportunity_score():
    score, parts = score_opportunity(
        {},
        {"premarket_change_pct": 80},
        now=datetime(2026, 9, 25, 12, tzinfo=timezone.utc),
    )
    assert score == 10
    assert parts["market_movement"] == 10
    assert parts["catalyst"] == 0


def test_confirmed_fresh_catalyst_can_reach_100():
    now = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
    score, parts = score_opportunity(
        {
            "score": 100,
            "catalyst_confirmation": "CONFIRMED",
            "market_impact_score": 100,
            "novelty_score": 100,
            "event_surprise": "HIGH",
            "_ts": now,
        },
        {"premarket_change_pct": 50},
        now=now,
    )
    assert score == 100
    assert parts["catalyst"] == 30
    assert parts["confidence"] == 20
    assert parts["clinical_impact"] == 15
    assert parts["novelty"] == 10
    assert parts["timing"] == 10
    assert parts["market_movement"] == 10
    assert parts["surprise"] == 5


def test_yahoo_premarket_metadata_is_parsed():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "chart": {
            "result": [{
                "meta": {
                    "previousClose": 10,
                    "preMarketPrice": 12,
                    "preMarketChangePercent": 20,
                    "preMarketVolume": 123456,
                },
                "indicators": {"quote": [{}]},
            }]
        }
    }
    session = Mock()
    session.get.return_value = response
    result = get_premarket_snapshot("TEST", session=session)
    assert result["premarket_price"] == 12
    assert result["premarket_change_pct"] == 20
    assert result["premarket_volume"] == 123456


def test_format_report_includes_next_catalysts():
    report = format_report(
        [{
            "ticker": "ABC",
            "company": "ABC Pharma",
            "program": "Drug A",
            "catalyst": {"title": "FDA event", "source": "FDA"},
            "snapshot": {"premarket_change_pct": 12},
            "opportunity_score": 70,
            "confidence": "CONFIRMED",
        }],
        now=datetime(2026, 9, 29, 12, tzinfo=timezone.utc),
        calendar_rows=[{
            "date": "2026-10-02",
            "date_precision": "DAY",
            "ticker": "ABC",
            "programs": ["Drug A"],
            "milestone": "PRIMARY_COMPLETION",
        }],
    )
    assert "NEXT CATALYSTS" in report
    assert "2026-10-02" in report
    assert "PRIMARY_COMPLETION" in report
