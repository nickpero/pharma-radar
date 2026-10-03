"""Pharma Radar — unified early discovery + EMA + SEC catalyst pipeline."""
from __future__ import annotations

from scanner.fda_matcher import identify_fda_target
from scanner.fda_catalyst import build_fda_catalyst
from scanner.fda_score import score_fda_event
from scanner.trading_intelligence import enrich_trading_event
from scanner.priority import enrich_alert_priority, sort_by_alert_priority
from scanner.ema_feed import get_ema_news
from scanner.early_discovery_feed import get_early_news
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
        "content": item.get("content", ""),
        "published_at": item.get("published_at"),
        "first_published_at": item.get("first_published_at") or item.get("published_at"),
        "first_seen_at": item.get("first_seen_at"),
        "event_date": item.get("event_date") or item.get("published_at"),
        "early_discovery": bool(item.get("early_discovery")),
        "provider": item.get("provider"),
        "source_reliability": item.get("source_reliability"),
    })
    event = enrich_clinical_impact(event)
    scored = score_fda_event(event)
    trading = enrich_trading_event(scored)
    trading = enrich_alert_priority(trading)
    trading["pipeline"] = item.get("source", "REGULATORY")
    trading["pipeline_stage"] = "TRADING_INTELLIGENCE"

    event_date = trading.get("event_date") or trading.get("published_at")
    subtype = str(trading.get("subtype") or "UNKNOWN").strip().lower()
    trading["event_key"] = "|".join(str(value or "UNKNOWN").strip().lower() for value in (
        trading.get("ticker"), trading.get("program"), subtype, str(event_date)[:10]
    ))
    return trading


def process_regulatory_news(items, watchlist):
    results = []
    seen = set()
    for item in items or []:
        event = _process_item(item, watchlist)
        if event is None:
            continue
        fingerprint = event.get("event_key") or (
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
    early_news = get_early_news(watchlist)
    ema_news = get_ema_news(max_items=ema_max)
    sec_news = get_sec_news(watchlist, max_filings_per_company=sec_per_company)
    all_news = early_news + ema_news + sec_news
    events = process_regulatory_news(all_news, watchlist)
    return {
        "early_news": early_news,
        "ema_news": ema_news,
        "sec_news": sec_news,
        "news": all_news,
        "events": events,
        "alerts": [event for event in events if event.get("trading_impact") in {"EXTREME", "HIGH"}],
    }
