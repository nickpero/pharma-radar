from datetime import datetime, timezone

from scanner.fda_freshness import is_stale_fda_item


NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def test_rejects_historical_fda_news():
    item = {
        "url": "https://www.fda.gov/news-events/press-announcements/old-item",
        "published_at": "2020-05-12T10:00:00Z",
    }
    assert is_stale_fda_item(item, now=NOW)


def test_rejects_wayback_archive_even_if_date_is_missing():
    item = {"url": "https://web.archive.org/web/20200101/https://www.fda.gov/old"}
    assert is_stale_fda_item(item, now=NOW)


def test_keeps_recent_fda_announcement():
    item = {
        "url": "https://www.fda.gov/news-events/press-announcements/new-item",
        "published_at": "2026-10-13T18:45:00Z",
    }
    assert not is_stale_fda_item(item, now=NOW)


def test_keeps_unknown_date_for_review_instead_of_guessing():
    assert not is_stale_fda_item({"published_at": "date unavailable"}, now=NOW)
