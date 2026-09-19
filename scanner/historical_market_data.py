"""Daily market-data provider for the Historical Edge Engine.

The historical backfill can contain many catalysts for the same ticker across
many years. Fetching a separate Yahoo request for every event/date pair makes
the provider unnecessarily request-heavy and can trigger rate limits. This
adapter therefore caches fixed multi-year chunks per symbol and retries
transient failures. A Stooq CSV fallback is used when Yahoo cannot provide a
chunk.
"""

from __future__ import annotations

import csv
import io
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping

import requests

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
STOOQ_DAILY_URL = "https://stooq.com/q/d/l/"
CHUNK_YEARS = 5
MAX_RETRIES = 3
RETRY_DELAYS = (1.0, 2.0, 4.0)


class YahooDailyProvider:
    """Fetch and cache daily OHLCV observations for one historical run."""

    def __init__(self, timeout: int = 20, session: requests.Session | None = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self._cache: dict[tuple[str, date, date], dict[str, dict[str, Any]]] = {}
        self._symbol_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self._chunk_source: dict[tuple[str, str], str] = {}
        self._source_counts: dict[str, int] = {"Yahoo": 0, "Stooq": 0, "Failed": 0}

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
            pass
        try:
            return parsedate_to_datetime(text).date()
        except (TypeError, ValueError, OverflowError):
            pass
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

    @staticmethod
    def _chunks(start: date, end: date):
        """Yield fixed 5-year blocks so nearby events share the same cache."""
        cursor_year = (start.year // CHUNK_YEARS) * CHUNK_YEARS
        cursor = date(cursor_year, 1, 1)
        while cursor <= end:
            chunk_end = date(cursor.year + CHUNK_YEARS - 1, 12, 31)
            yield cursor, chunk_end
            cursor = date(cursor.year + CHUNK_YEARS, 1, 1)

    def _request(self, method: str, url: str, **kwargs):
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
                response.raise_for_status()
                return response
            except (requests.RequestException, ValueError) as error:
                last_error = error
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[attempt])
        raise last_error or RuntimeError("market-data request failed")

    def _fetch_yahoo_chunk(self, symbol: str, start: date, end: date) -> dict[str, dict[str, Any]]:
        period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
        period2 = int(datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
        response = self._request(
            "GET",
            YAHOO_CHART_URL.format(symbol=symbol),
            params={"period1": period1, "period2": period2, "interval": "1d", "events": "history"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; Pharma-Radar/1.0)"},
        )
        payload = response.json()
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            raise ValueError(f"No Yahoo chart data for {symbol}")
        chart = result[0]
        timestamps = chart.get("timestamp") or []
        quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []
        rows: dict[str, dict[str, Any]] = {}
        for index, timestamp in enumerate(timestamps):
            day = datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
            close = closes[index] if index < len(closes) else None
            volume = volumes[index] if index < len(volumes) else None
            if close is None:
                continue
            rows[day] = {"close": float(close), "volume": volume}
        return rows

    def _fetch_stooq_chunk(self, symbol: str, start: date, end: date) -> dict[str, dict[str, Any]]:
        stooq_symbol = f"{symbol.lower()}.us"
        response = self._request(
            "GET",
            STOOQ_DAILY_URL,
            params={"s": stooq_symbol, "d1": start.strftime("%Y%m%d"), "d2": end.strftime("%Y%m%d"), "i": "d"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; Pharma-Radar/1.0)"},
        )
        text = response.text.strip()
        if not text or text.lower().startswith("no data"):
            raise ValueError(f"No Stooq data for {symbol}")
        rows: dict[str, dict[str, Any]] = {}
        for row in csv.DictReader(io.StringIO(text)):
            day = str(row.get("Date") or "").strip()
            close = row.get("Close")
            if not day or close in (None, ""):
                continue
            try:
                rows[day] = {"close": float(close), "volume": float(row["Volume"]) if row.get("Volume") else None}
            except (TypeError, ValueError):
                continue
        if not rows:
            raise ValueError(f"No Stooq rows for {symbol}")
        return rows

    def _fetch_chunk(self, symbol: str, start: date, end: date) -> dict[str, dict[str, Any]]:
        chunk_key = f"{start.isoformat()}:{end.isoformat()}"
        try:
            rows = self._fetch_yahoo_chunk(symbol, start, end)
            self._chunk_source[(symbol, chunk_key)] = "Yahoo"
            self._source_counts["Yahoo"] += 1
            return rows
        except Exception as yahoo_error:
            try:
                rows = self._fetch_stooq_chunk(symbol, start, end)
                self._chunk_source[(symbol, chunk_key)] = "Stooq"
                self._source_counts["Stooq"] += 1
                return rows
            except Exception as stooq_error:
                self._chunk_source[(symbol, chunk_key)] = "Failed"
                self._source_counts["Failed"] += 1
                raise RuntimeError(
                    f"No market data for {symbol} {start}..{end}; "
                    f"Yahoo={yahoo_error}; Stooq={stooq_error}"
                ) from stooq_error

    def _fetch_symbol(self, symbol: str, start: date, end: date) -> dict[str, dict[str, Any]]:
        symbol = str(symbol).upper().strip()
        if not symbol:
            return {}
        cache_key = (symbol, start, end)
        if cache_key in self._cache:
            return self._cache[cache_key]

        combined = self._symbol_cache.setdefault(symbol, {})
        for chunk_start, chunk_end in self._chunks(start, end):
            chunk_key = f"{chunk_start.isoformat()}:{chunk_end.isoformat()}"
            if chunk_key not in combined:
                combined[chunk_key] = self._fetch_chunk(symbol, chunk_start, chunk_end)

        rows: dict[str, dict[str, Any]] = {}
        for chunk_rows in combined.values():
            for day, row in chunk_rows.items():
                day_value = self._date(day)
                if day_value is not None and start <= day_value <= end:
                    rows[day] = dict(row)
        self._cache[cache_key] = rows
        return rows

    @staticmethod
    def _event_date(event: Mapping[str, Any]) -> date | None:
        return YahooDailyProvider._date(event.get("event_timestamp") or event.get("published_at"))

    def get_event_bars(self, event: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        event_date = self._event_date(event)
        if event_date is None:
            return {"event": {}}
        rows = self._fetch_symbol(
            str(event.get("ticker") or ""),
            event_date - timedelta(days=40),
            event_date + timedelta(days=10),
        )
        return self._window_bars(rows, event_date)

    def get_benchmark_bars(self, event: Mapping[str, Any], benchmark: str) -> dict[str, dict[str, Any]]:
        event_date = self._event_date(event)
        if event_date is None:
            return {"event": {}}
        rows = self._fetch_symbol(
            benchmark,
            event_date - timedelta(days=40),
            event_date + timedelta(days=10),
        )
        return self._window_bars(rows, event_date)

    def source_for(self, symbol: str, event_date: date | None) -> str:
        if event_date is None:
            return "UNKNOWN"
        year = (event_date.year // CHUNK_YEARS) * CHUNK_YEARS
        start = date(year, 1, 1)
        end = date(year + CHUNK_YEARS - 1, 12, 31)
        return self._chunk_source.get((str(symbol).upper().strip(), f"{start.isoformat()}:{end.isoformat()}"), "UNKNOWN")

    def stats(self) -> dict[str, Any]:
        return {
            "source_chunks": dict(self._source_counts),
            "cached_chunks": sum(len(chunks) for chunks in self._symbol_cache.values()),
        }

    @staticmethod
    def _window_bars(rows: Mapping[str, Mapping[str, Any]], event_date: date) -> dict[str, dict[str, Any]]:
        dates = sorted(date.fromisoformat(value) for value in rows if value)
        future = [value for value in dates if value >= event_date]
        result: dict[str, dict[str, Any]] = {"event": {}}
        if not future:
            return result
        event_day = future[0]
        event_row = dict(rows[event_day.isoformat()])
        prior = [
            rows[value.isoformat()].get("volume")
            for value in dates
            if value < event_day and rows[value.isoformat()].get("volume") is not None
        ][-20:]
        if prior:
            event_row["baseline_volume"] = sum(float(value) for value in prior) / len(prior)
        result["event"] = event_row
        for offset, window in ((1, "1D"), (3, "3D"), (5, "5D")):
            if len(future) > offset:
                result[window] = dict(rows[future[offset].isoformat()])
        return result
