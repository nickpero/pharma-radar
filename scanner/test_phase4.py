from datetime import datetime, timezone

from scanner.market_profile import get_market_profile
from scanner.market_data import enrich_market_data
import scanner.market_data as market_data_module
from scanner.trading_setup import (
    infer_event_surprise,
    surprise_score,
    market_cap_score,
    short_interest_score,
    build_trading_setup,
    enrich_trading_setup,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload

    def get(self, *args, **kwargs):
        return FakeResponse(self.payload)


def test_market_profile_parses_cap_and_short_interest():
    payload = {
        "quoteSummary": {
            "result": [{
                "price": {"marketCap": {"raw": 750_000_000}},
                "defaultKeyStatistics": {"shortPercentOfFloat": {"raw": 0.125}},
            }]
        }
    }
    result = get_market_profile("TEST", session=FakeSession(payload))
    assert result["market_cap"] == 750_000_000
    assert result["short_interest_pct"] == 12.5


def test_event_surprise_is_conservative():
    assert infer_event_surprise({"title": "Results beat expectations"}) == "UNEXPECTED"
    assert infer_event_surprise({"title": "Results were in line with expectations"}) == "EXPECTED"
    assert infer_event_surprise({"title": "FDA approval announced"}) == "UNKNOWN"
    assert surprise_score("UNEXPECTED") > surprise_score("EXPECTED")


def test_market_cap_and_short_interest_scores():
    assert market_cap_score(250_000_000) == 4
    assert market_cap_score(10_000_000_000) == 1
    assert short_interest_score(25) == 4
    assert short_interest_score(2) == 1


def test_phase4_inputs_change_setup_score():
    base = {
        "score": 70,
        "trading_impact": "HIGH",
        "urgency": "FAST",
        "match_confidence": "HIGH",
        "direction": "POSITIVE",
        "published_at": "2026-09-07T08:00:00+00:00",
    }
    now = datetime(2026, 9, 7, 8, 5, tzinfo=timezone.utc)
    low = build_trading_setup(base, market_data={"price_change_pct": 1, "volume_ratio": 1}, now=now)
    rich = dict(base)
    rich.update({
        "event_surprise": "UNEXPECTED",
        "market_cap": 250_000_000,
        "short_interest_pct": 25,
    })
    high = build_trading_setup(rich, market_data={"price_change_pct": 1, "volume_ratio": 1}, now=now)
    assert high["trading_setup_score"] > low["trading_setup_score"]
    assert high["event_surprise_score"] == 7
    assert high["market_cap_score"] == 4
    assert high["short_interest_score"] == 4


def test_phase4_end_to_end_market_enrichment_to_setup():
    alert = {
        "ticker": "TEST",
        "score": 80,
        "trading_impact": "EXTREME",
        "urgency": "IMMEDIATE",
        "match_confidence": "HIGH",
        "direction": "POSITIVE",
        "title": "Results beat expectations",
        "published_at": "2026-09-07T08:00:00+00:00",
    }

    original_snapshot = market_data_module.get_market_snapshot
    original_profile = market_data_module.get_market_profile
    market_data_module.get_market_snapshot = lambda ticker: {
        "price_change_pct": 6.0,
        "volume_ratio": 3.5,
    }
    market_data_module.get_market_profile = lambda ticker: {
        "ticker": ticker,
        "market_cap": 250_000_000,
        "short_interest_pct": 25.0,
        "market_profile_source": "TEST",
    }
    try:
        enriched = enrich_market_data([alert])
    finally:
        market_data_module.get_market_snapshot = original_snapshot
        market_data_module.get_market_profile = original_profile

    assert enriched[0]["market_data"]["volume_ratio"] == 3.5
    assert enriched[0]["market_cap"] == 250_000_000
    assert enriched[0]["short_interest_pct"] == 25.0

    final = enrich_trading_setup(
        enriched[0],
        market_data=enriched[0].get("market_data"),
        now=datetime(2026, 9, 7, 8, 5, tzinfo=timezone.utc),
    )

    assert final["event_surprise"] == "UNEXPECTED"
    assert final["market_awareness"] == "MEDIUM"
    assert final["trading_window"] == "0-2H"
    assert final["trading_setup_score"] > 0
    assert final["market_cap_score"] == 4
    assert final["short_interest_score"] == 4


if __name__ == "__main__":
    test_market_profile_parses_cap_and_short_interest()
    test_event_surprise_is_conservative()
    test_market_cap_and_short_interest_scores()
    test_phase4_inputs_change_setup_score()
    test_phase4_end_to_end_market_enrichment_to_setup()
    print("Trading Intelligence Phase 4 tests passed")
