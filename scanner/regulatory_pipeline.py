"""Pharma Radar — unified EMA + SEC catalyst pipeline."""
from __future__ import annotations

from scanner.fda_matcher import identify_fda_target
from scanner.fda_catalyst import build_fda_catalyst
from scanner.fda_score import score_fda_event
from scanner.trading_intelligence import enrich_trading_event
from scanner.priority import enrich_alert_priority, sort_by_alert_priority
from scanner.ema_feed import get_ema_news
from scanner.sec_feed import get_sec_news
from scanner.clinical_impact import enrich_clinical_impact


def _process_item(item, watchlist):
    target = identify_fda_target(item, watchlist)
    if target is None:
        return None

    event = build_fda_catalyst(item)
    event.update({
        "ticker": target.get("ticker"),
        "company": target.get("company"),
        "program": target.get("program"),
        "match_type": target.get("match_type"),
        "match_confidence": target.get("confidence"),
        "company_matches": target.get("company_matches", []),
        "program_matches": target.get("program_matches", []),
        "source": item.get("source"),
        "source_type": item.get("source_type"),
        "source_item_id": item.get("item_id"),
        "url": item.get("url"),
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "published_at": item.get("published_at"),
    })
    event = enrich_clinical_impact(event)
    scored = score_fda_event(event)
    trading = enrich_trading_event(scored)
    trading = enrich_alert_priority(trading)
    trading["pipeline"] = item.get("source", "REGULATORY")
    trading["pipeline_stage"] = "TRADING_INTELLIGENCE"
    return trading


def process_regulatory_news(items, watchlist):
    results = []
    seen = set()
    for item in items or []:
        event = _process_item(item, watchlist)
        if event is None:
            continue
        fingerprint = (
            event.get("ticker"),
            event.get("program"),
            event.get("subtype"),
            event.get("published_at"),
            event.get("title"),
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        results.append(event)
    return sort_by_alert_priority(results)


def scan_regulatory_sources(watchlist, ema_max=50, sec_per_company=3):
    ema_news = get_ema_news(max_items=ema_max)
    sec_news = get_sec_news(watchlist, max_filings_per_company=sec_per_company)
    all_news = ema_news + sec_news
    events = process_regulatory_news(all_news, watchlist)
    return {
        "ema_news": ema_news,
        "sec_news": sec_news,
        "news": all_news,
        "events": events,
        "alerts": [event for event in events if event.get("trading_impact") in {"EXTREME", "HIGH"}],
    }
