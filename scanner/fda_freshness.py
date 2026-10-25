"""Freshness checks for FDA catalyst candidates."""
from datetime import datetime, timezone
from urllib.parse import urlparse


def is_stale_fda_item(item, now=None, max_age_days=30):
    if not isinstance(item, dict):
        return True
    url = str(item.get("url") or "")
    host = (urlparse(url).hostname or "").lower() if url else ""
    if host == "web.archive.org" or host.endswith(".web.archive.org"):
        return True
    raw = item.get("published_at") or item.get("event_timestamp") or item.get("event_date")
    if not raw:
        return False
    try:
        published = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return (current - published).total_seconds() > max(0, int(max_age_days)) * 86400
