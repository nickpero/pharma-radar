from datetime import datetime, timezone

from scanner.market_data import enrich_post_spike_watch
from scanner.telegram_intelligence import _dedup_key, _is_stale_news, alert_action


def _points():
    points = []
    for i in range(20):
        points.append({
            "date": datetime(2026, 8, 25 + i, tzinfo=timezone.utc).date(),
            "close": 90.0,
            "high": 92.0,
            "volume": 10.0,
        })
    points.extend([
        {"date": datetime(2026, 9, 22, tzinfo=timezone.utc).date(), "close": 100.0, "high": 102.0, "volume": 10.0},
        {"date": datetime(2026, 9, 23, tzinfo=timezone.utc).date(), "close": 150.0, "high": 170.0, "volume": 100.0},
        {"date": datetime(2026, 9, 24, tzinfo=timezone.utc).date(), "close": 125.0, "high": 130.0, "volume": 20.0},
        {"date": datetime(2026, 9, 25, tzinfo=timezone.utc).date(), "close": 120.0, "high": 125.0, "volume": 10.0},
    ])
    return points


def test_post_spike_watch(monkeypatch):
    monkeypatch.setattr("scanner.market_data.get_daily_series", lambda ticker, session=None, range_="2mo": _points())
    events = [{
        "ticker": "VTGN",
        "program": "fasedienol",
        "direction": "POSITIVE",
        "published_at": "2026-09-22",
    }]
    result = enrich_post_spike_watch(
        events,
        now=datetime(2026, 9, 27, tzinfo=timezone.utc),
    )[0]
    assert result["post_spike_watch"] is True
    assert result["market_reaction_state"] == "POST_SPIKE"
    assert result["post_spike_pct"] == 50.0
    assert result["post_spike_volume_ratio"] == 10.0
    assert result["post_spike_retracement_pct"] == -20.0


def test_post_spike_requires_retracement(monkeypatch):
    monkeypatch.setattr("scanner.market_data.get_daily_series", lambda ticker, session=None, range_="2mo": _points()[:-1] + [{
        "date": datetime(2026, 9, 25, tzinfo=timezone.utc).date(), "close": 145.0, "high": 150.0, "volume": 10.0
    }])
    event = {"ticker": "VTGN", "program": "fasedienol", "direction": "POSITIVE", "published_at": "2026-09-22"}
    result = enrich_post_spike_watch([event], now=datetime(2026, 9, 27, tzinfo=timezone.utc))[0]
    assert result["post_spike_watch"] is False


def test_stale_regulatory_news_is_silent():
    alert = {
        "source": "SEC",
        "source_type": "PRIMARY_CORPORATE",
        "published_at": "2026-09-22",
    }
    now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
    assert _is_stale_news(alert, now=now) is True
    assert alert_action(alert) == "SILENT"


def test_subtype_change_does_not_change_identity():
    base = {
        "ticker": "VTGN",
        "program": "fasedienol",
        "title": "SEC 8-K — Vistagen Therapeutics (VTGN)",
        "event_timestamp": "2026-09-22",
    }
    first = dict(base, subtype="PHASE_ADVANCED")
    second = dict(base, subtype="PHASE_DATA_UPDATE")
    assert _dedup_key(first) == _dedup_key(second)


def test_post_spike_gets_separate_delivery_state():
    base = {
        "ticker": "VTGN",
        "program": "fasedienol",
        "title": "SEC 8-K — Vistagen Therapeutics (VTGN)",
        "event_timestamp": "2026-09-22",
    }
    normal = _dedup_key(base)
    watch = _dedup_key(dict(base, post_spike_watch=True))
    assert normal != watch
    assert alert_action(dict(base, post_spike_watch=True)) == "WATCH"
