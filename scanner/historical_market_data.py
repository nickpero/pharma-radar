"""Daily market-data provider for the Historical Edge Engine.

The analytics layer stays vendor-neutral.  This module provides a small
Yahoo Finance chart-API adapter using the already-installed ``requests``
package.  It is intentionally used by the historical batch job rather than
by every 15-minute production scan.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

import requests


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class YahooDailyProvider:
    """Fetch and cache daily OHLCV observations for one historical run."""

    def __init__(self, timeout: int = 15, session: requests.Session | None = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self._cache: dict[str, dict[str, dict[str, Any]]] = {}

    @staticmethod
    def _date(value: Any) -> date | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(text[:10])
            except ValueError:
                return None

    def _fetch_symbol(self, symbol: str, start: date, end: date) -> dict[str, dict[str, Any]]:
        symbol = str(symbol).upper().strip()
        if not symbol:
            return {}
        cache_key = symbol
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        period2 = int(datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
        response = self.session.get(
            YAHOO_CHART_URL.format(symbol=symbol),
            params={"period1": period1, "period2": period2, "interval": "1d", "events": "history"},
            headers={"User-Agent": "Pharma-Radar/1.0"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            raise ValueError(f"No Yahoo chart data for {symbol}")

        chart = result[0]
        timestamps = chart.get("timestamp") or []
        quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
        rows: dict[str, dict[str, Any]] = {}
        for index, timestamp in enumerate(timestamps):
            day = datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
            close = (quote.get("close") or [None] * len(timestamps))[index]
            volume = (quote.get("volume") or [None] * len(timestamps))[index]
            if close is None:
                continue
            rows[day] = {"close": float(close), "volume": volume}
        self._cache[cache_key] = rows
        return rows

    @staticmethod
    def _event_date(event: Mapping[str, Any]) -> date | None:
        return YahooDailyProvider._date(event.get("event_timestamp") or event.get("published_at"))

    def get_event_bars(self, event: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        """Return event-day close plus +1/+3/+5 trading-day closes.

        The event-day close is the daily anchor.  The provider deliberately
        does not pretend to know whether a catalyst arrived before or after
        the close; intraday timing remains a later enhancement.
        """
        event_date = self._event_date(event)
        if event_date is None:
            return {"event": {}}
        rows = self._fetch_symbol(str(event.get("ticker") or ""), event_date - timedelta(days=7), event_date + timedelta(days=10))
        return self._window_bars(rows, event_date)

    def get_benchmark_bars(self, event: Mapping[str, Any], benchmark: str) -> dict[str, dict[str, Any]]:
        event_date = self._event_date(event)
        if event_date is None:
            return {"event": {}}
        rows = self._fetch_symbol(benchmark, event_date - timedelta(days=7), event_date + timedelta(days=10))
        return self._window_bars(rows, event_date)

    @staticmethod
    def _window_bars(rows: Mapping[str, Mapping[str, Any]], event_date: date) -> dict[str, dict[str, Any]]:
        dates = sorted(date.fromisoformat(value) for value in rows if value)
        future = [value for value in dates if value >= event_date]
        result: dict[str, dict[str, Any]] = {"event": {}}
        if not future:
            return result
        event_day = future[0]
        result["event"] = dict(rows[event_day.isoformat()])
        for offset, window in ((1, "1D"), (3, "3D"), (5, "5D")):
            if len(future) > offset:
                result[window] = dict(rows[future[offset].isoformat()])
        return result
