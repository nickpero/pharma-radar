"""Structural validation for the Pharma Radar watchlist.

This checks metadata consistency only; it does not certify that a drug/program
is current or that every external source is reachable.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"
ALLOWED_PRIORITIES = {"RED", "ORANGE"}


def validate_watchlist(watchlist: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(watchlist, dict) or not watchlist:
        return ["watchlist must be a non-empty JSON object"]

    for ticker, entry in watchlist.items():
        if not isinstance(ticker, str) or not re.fullmatch(r"[A-Z0-9.\-]{1,12}", ticker):
            errors.append(f"{ticker!r}: invalid ticker key")
            continue
        if not isinstance(entry, dict):
            errors.append(f"{ticker}: entry must be an object")
            continue
        if not isinstance(entry.get("company"), str) or not entry["company"].strip():
            errors.append(f"{ticker}: missing company name")
        programs = entry.get("programs")
        if not isinstance(programs, list) or not programs:
            errors.append(f"{ticker}: programs must be a non-empty list")
        elif any(not isinstance(p, str) or not p.strip() for p in programs):
            errors.append(f"{ticker}: programs contain an empty/non-string value")
        if entry.get("priority") not in ALLOWED_PRIORITIES:
            errors.append(f"{ticker}: priority must be one of {sorted(ALLOWED_PRIORITIES)}")
        sources = entry.get("primary_sources")
        if sources is not None and (
            not isinstance(sources, list)
            or any(not isinstance(s, str) or not s.strip() for s in sources)
        ):
            errors.append(f"{ticker}: primary_sources must be a list of non-empty strings")
    return errors


def main() -> int:
    watchlist = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    errors = validate_watchlist(watchlist)
    print(f"WATCHLIST QUALITY: companies={len(watchlist)} errors={len(errors)}")
    for error in errors:
        print(f"WATCHLIST QUALITY ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
