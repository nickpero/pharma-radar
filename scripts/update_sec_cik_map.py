"""Refresh SEC CIK mappings for the configured Pharma Radar watchlist.

Uses the SEC's official company_tickers_exchange.json file. Hand-maintained
high-priority mappings in scanner.sec_feed.WATCHLIST_CIK remain authoritative;
the official feed fills and refreshes the supplemental mappings for the rest.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"
MAP_PATH = ROOT / "data" / "sec_cik_map.json"
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_CIK_NAME_URL = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"
TIMEOUT_SECONDS = 30


def normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def normalize_cik(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text.isdigit():
        return None
    return text.zfill(10)


def normalize_company_name(value: Any) -> str:
    """Normalize a company name conservatively for exact historical CIK matching."""
    text = re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()
    tokens = text.split()
    legal_suffixes = {
        "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY",
        "LTD", "LIMITED", "PLC", "LLC", "LP",
    }
    while tokens and tokens[-1] in legal_suffixes:
        tokens.pop()
    return " ".join(tokens)


def parse_sec_cik_lookup_text(text: str) -> dict[str, list[str]]:
    """Parse SEC's cumulative filer-name list into normalized name -> unique CIKs."""
    index: dict[str, set[str]] = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip().rstrip(":")
        if not line:
            continue
        name, separator, raw_cik = line.rpartition(":")
        if not separator:
            continue
        normalized_name = normalize_company_name(name)
        cik = normalize_cik(raw_cik)
        if normalized_name and cik:
            index.setdefault(normalized_name, set()).add(cik)
    return {name: sorted(ciks) for name, ciks in index.items()}


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
    historical_name_index: dict[str, list[str]] | None = None,
) -> tuple[dict[str, str], dict[str, int]]:
    """Build a map only for watched issuers, preferring protected manual entries."""
    existing_map = existing_map or {}
    protected_map = protected_map or {}
    historical_name_index = historical_name_index or {}
    result: dict[str, str] = {}
    counts = {"protected": 0, "official": 0, "fallback": 0, "historical_name": 0, "unmapped": 0, "excluded": 0}

    for raw_ticker, config in watchlist.items():
        ticker = normalize_ticker(raw_ticker)
        if not ticker:
            continue
        if isinstance(config, dict) and config.get("sec_monitoring") is False:
            counts["excluded"] += 1
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
            company_names = []
            if isinstance(config, dict):
                company_names.append(config.get("company", ""))
                company_names.extend(config.get("sec_name_aliases", []) or [])
            candidate_ciks = set()
            for company_name in company_names:
                candidate_ciks.update(
                    historical_name_index.get(normalize_company_name(company_name), [])
                )
            if len(candidate_ciks) == 1:
                result[ticker] = next(iter(candidate_ciks))
                counts["historical_name"] += 1
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


def fetch_sec_cik_name_index(user_agent: str) -> dict[str, list[str]]:
    """Download the SEC's cumulative filer-name/CIK index, including historical filers."""
    if not user_agent.strip():
        raise RuntimeError(
            "SEC_USER_AGENT is missing. Configure a descriptive contact string "
            "in the GitHub repository secret SEC_USER_AGENT."
        )
    response = requests.get(
        SEC_CIK_NAME_URL,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": user_agent.strip(), "Accept": "text/plain"},
    )
    response.raise_for_status()
    text = response.content.decode("latin-1", errors="replace")
    index = parse_sec_cik_lookup_text(text)
    if len(index) < 1000:
        raise RuntimeError(
            f"SEC cumulative CIK name index validation failed: only {len(index)} names parsed."
        )
    return index


def main() -> int:
    with WATCHLIST_PATH.open("r", encoding="utf-8") as handle:
        watchlist = json.load(handle)
    with MAP_PATH.open("r", encoding="utf-8") as handle:
        existing_map = json.load(handle)

    from scanner.sec_feed import WATCHLIST_CIK

    user_agent = os.getenv("SEC_USER_AGENT", "")
    official_map = fetch_official_map(user_agent)
    historical_name_index = fetch_sec_cik_name_index(user_agent)
    updated_map, counts = build_watchlist_cik_map(
        watchlist, official_map, existing_map, WATCHLIST_CIK, historical_name_index
    )
    content = json.dumps(updated_map, indent=2, ensure_ascii=False) + "\n"
    previous_content = MAP_PATH.read_text(encoding="utf-8")
    print(
        "SEC CIK MAP REFRESH: "
        f"watchlist={len(watchlist)} mapped={len(updated_map)} "
        f"official={counts['official']} protected={counts['protected']} "
        f"fallback={counts['fallback']} historical_name={counts['historical_name']} "
        f"unmapped={counts['unmapped']} "
        f"excluded={counts['excluded']}",
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
