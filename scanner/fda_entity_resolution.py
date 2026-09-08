"""Pharma Radar — FDA Entity Resolution (Phase 5.9A).

Resolves structured watchlist entities from an official FDA article after
body enrichment, without weakening the strict FDA matcher.
"""

from __future__ import annotations

from scanner.fda_matcher import (
    build_news_text,
    get_company_aliases,
    get_program_aliases,
    load_watchlist,
    contains_alias,
    contains_ticker,
)


def _best_alias_match(text: str, aliases: list[str]) -> str | None:
    """Return the longest matching alias, preferring specific names."""
    matches = [alias for alias in aliases if contains_alias(text, alias)]
    if not matches:
        return None
    return max(matches, key=lambda value: len(str(value)))


def resolve_fda_entities(news_item: dict, watchlist=None) -> dict:
    """Attach structured FDA entity-resolution evidence to a news item.

    Safety rule: this function never invents a ticker/program. It only records
    entities already present in the supplied watchlist and visible in the
    official FDA article text.
    """
    if not isinstance(news_item, dict):
        raise TypeError("news_item must be a dictionary")

    watchlist = load_watchlist() if watchlist is None else watchlist
    if not isinstance(watchlist, dict):
        raise TypeError("watchlist must be a dictionary")

    text = build_news_text(news_item)
    if not text:
        return dict(news_item)

    candidates = []
    for ticker, company in watchlist.items():
        if not isinstance(company, dict):
            continue

        company_alias = _best_alias_match(
            text,
            get_company_aliases(ticker, company),
        )
        ticker_match = contains_ticker(news_item, ticker)

        for program in company.get("programs", []) or []:
            program_alias = _best_alias_match(
                text,
                get_program_aliases(ticker, program),
            )
            if not company_alias and not ticker_match and not program_alias:
                continue

            if program_alias and (company_alias or ticker_match):
                confidence = "HIGH"
                resolution_type = "COMPANY_AND_PROGRAM"
            elif program_alias:
                confidence = "HIGH"
                resolution_type = "PROGRAM"
            else:
                confidence = "MEDIUM"
                resolution_type = "COMPANY"

            candidates.append({
                "ticker": ticker,
                "company": company.get("company", ticker),
                "program": program,
                "company_evidence": company_alias or (ticker if ticker_match else None),
                "program_evidence": program_alias,
                "resolution_type": resolution_type,
                "confidence": confidence,
            })

    if not candidates:
        return dict(news_item)

    candidates.sort(
        key=lambda item: (
            2 if item["resolution_type"] == "COMPANY_AND_PROGRAM" else 1 if item["resolution_type"] == "PROGRAM" else 0,
            len(str(item.get("program_evidence") or "")),
            len(str(item.get("company_evidence") or "")),
        ),
        reverse=True,
    )

    resolved = dict(news_item)
    best = candidates[0]
    resolved["fda_entity_resolution"] = {
        "status": "RESOLVED",
        "ticker": best["ticker"],
        "company": best["company"],
        "program": best["program"],
        "company_evidence": best["company_evidence"],
        "program_evidence": best["program_evidence"],
        "resolution_type": best["resolution_type"],
        "confidence": best["confidence"],
        "candidate_count": len(candidates),
    }
    return resolved
