"""Pharma Radar universe expansion and reconciliation.

Candidates are reviewed externally, then admitted only when they have a valid
SEC CIK and a complete ticker/company/program mapping. This keeps discovery
separate from catalyst qualification and prevents speculative movers from
silently entering the production universe.
"""

import json
from pathlib import Path

WATCHLIST_FILE = Path("data/watchlist.json")
CIK_FILE = Path("data/sec_cik_map.json")
CANDIDATE_FILE = Path("data/universe_candidates.json")


def _load(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def reconcile_watchlist():
    watchlist = _load(WATCHLIST_FILE)
    cik_map = _load(CIK_FILE)
    registry = _load(CANDIDATE_FILE).get("candidates", {})
    added = []
    rejected = []

    for ticker, candidate in registry.items():
        ticker = str(ticker).upper().strip()
        company = str(candidate.get("company", "")).strip()
        programs = [str(p).strip() for p in candidate.get("programs", []) if str(p).strip()]
        cik = str(candidate.get("cik") or cik_map.get(ticker) or "").strip().zfill(10)
        if not ticker or not company or not programs or not cik or cik == "0000000000":
            rejected.append({"ticker": ticker, "reason": "INCOMPLETE_MAPPING"})
            continue
        if ticker in watchlist:
            continue
        if ticker not in cik_map:
            rejected.append({"ticker": ticker, "reason": "MISSING_SEC_CIK"})
            continue
        watchlist[ticker] = {
            "company": company,
            "programs": programs,
            "priority": candidate.get("priority", "ORANGE"),
        }
        added.append(ticker)

    if added:
        WATCHLIST_FILE.write_text(json.dumps(watchlist, indent=2) + "\n", encoding="utf-8")

    return {"watchlist": watchlist, "added": added, "rejected": rejected}


def load_expanded_watchlist():
    return reconcile_watchlist()["watchlist"]
