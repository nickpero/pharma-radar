"""Refresh SEC CIK mappings for the configured Pharma Radar watchlist.

Uses the SEC's official company_tickers_exchange.json file. Hand-maintained
high-priority mappings in scanner.sec_feed.WATCHLIST_CIK remain authoritative;
the official feed fills and refreshes the supplemental mappings for the rest.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"
MAP_PATH = ROOT / "data" / "sec_cik_map.json"
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
TIMEOUT_SECONDS = 30


def normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def normalize_cik(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text.isdigit():
        return None
    return text.zfill(10)


def parse_sec_ticker_payload(payload: Any) -> dict[str, str]:
    """Parse SEC exchange-map or company_tickers JSON into ticker -> 10-digit CIK."""
    result: dict[str, str] = {}
    if not isinstance(payload, dict):
        return result

    # Current company_tickers_exchange.json schema.
    fields = payload.get("fields")
    rows = payload.get("data")
    if isinstance(fields, list) and isinstance(rows, list):
        try:
            cik_idx = fields.index("cik")
            ticker_idx = fields.index("ticker")
        except ValueError:
            return result
        for row in rows:
            if not isinstance(row, list) or max(cik_idx, ticker_idx) >= len(row):
                continue
            ticker = normalize_ticker(row[ticker_idx])
            cik = normalize_cik(row[cik_idx])
            if ticker and cik:
                result[ticker] = cik
        return result

    # Legacy company_tickers.json schema: numeric keys -> objects.
    for row in payload.values():
        if not isinstance(row, dict):
            continue
        ticker = normalize_ticker(row.get("ticker"))
        cik = normalize_cik(row.get("cik_str", row.get("cik")))
        if ticker and cik:
            result[ticker] = cik
    return result


def build_watchlist_cik_map(
    watchlist: dict[str, Any],
    official_map: dict[str, str],
    existing_map: dict[str, str] | None = None,
    protected_map: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, int]]:
    """Build a map only for watched issuers, preferring protected manual entries."""
    existing_map = existing_map or {}
    protected_map = protected_map or {}
    result: dict[str, str] = {}
    counts = {"protected": 0, "official": 0, "fallback": 0, "unmapped": 0}

    for raw_ticker in watchlist:
        ticker = normalize_ticker(raw_ticker)
        if not ticker:
            continue
        protected = normalize_cik(protected_map.get(ticker))
        official = normalize_cik(official_map.get(ticker))
        existing = normalize_cik(existing_map.get(ticker))
        if protected:
            result[ticker] = protected
            counts["protected"] += 1
        elif official:
            result[ticker] = official
            counts["official"] += 1
        elif existing:
            result[ticker] = existing
            counts["fallback"] += 1
        else:
            counts["unmapped"] += 1

    return dict(sorted(result.items())), counts


def fetch_official_map(user_agent: str) -> dict[str, str]:
    if not user_agent.strip():
        raise RuntimeError(
            "SEC_USER_AGENT is missing. Configure a descriptive contact string "
            "in the GitHub repository secret SEC_USER_AGENT."
        )
    response = requests.get(
        SEC_TICKER_URL,
        timeout=TIMEOUT_SECONDS,
        headers={
            "User-Agent": user_agent.strip(),
            "Accept": "application/json",
        },
    )
    response.raise_for_status()
    payload = response.json()
    mapping = parse_sec_ticker_payload(payload)
    if len(mapping) < 1000:
        raise RuntimeError(
            f"SEC ticker map validation failed: only {len(mapping)} ticker mappings parsed."
        )
    return mapping


def main() -> int:
    with WATCHLIST_PATH.open("r", encoding="utf-8") as handle:
        watchlist = json.load(handle)
    with MAP_PATH.open("r", encoding="utf-8") as handle:
        existing_map = json.load(handle)

    from scanner.sec_feed import WATCHLIST_CIK

    official_map = fetch_official_map(os.getenv("SEC_USER_AGENT", ""))
    updated_map, counts = build_watchlist_cik_map(
        watchlist, official_map, existing_map, WATCHLIST_CIK
    )
    content = json.dumps(updated_map, indent=2, ensure_ascii=False) + "\n"
    previous_content = MAP_PATH.read_text(encoding="utf-8")
    print(
        "SEC CIK MAP REFRESH: "
        f"watchlist={len(watchlist)} mapped={len(updated_map)} "
        f"official={counts['official']} protected={counts['protected']} "
        f"fallback={counts['fallback']} unmapped={counts['unmapped']}",
        flush=True,
    )
    if content == previous_content:
        print("SEC CIK MAP unchanged.", flush=True)
        return 0

    MAP_PATH.write_text(content, encoding="utf-8")
    print(f"SEC CIK MAP updated: {MAP_PATH.relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
