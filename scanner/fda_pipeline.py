"""
Pharma Radar — FDA Pipeline

Pipeline completa per le FDA News:

FDA News
    ↓
FDA Article Enrichment
    ↓
FDA Matcher
    ↓
FDA Catalyst
    ↓
FDA Score
    ↓
Trading Intelligence
    ↓
Unified Alert Priority

Il modulo NON invia Telegram.
"""

from scanner.fda_news import filter_fda_catalysts
from scanner.fda_enrichment import enrich_fda_news_item
from scanner.fda_matcher import identify_fda_target
from scanner.fda_catalyst import build_fda_catalyst
from scanner.fda_score import score_fda_event
from scanner.trading_intelligence import enrich_trading_event
from scanner.priority import enrich_alert_priority, sort_by_alert_priority


def process_fda_news_item(news_item, watchlist=None):
    """Processa una singola FDA News Item end-to-end."""
    if not isinstance(news_item, dict):
        raise TypeError("news_item must be a dictionary")

    has_article_body = any(
        len(str(news_item.get(field) or "").strip()) >= 200
        for field in ("article_text", "content", "body", "text")
    )
    enriched_item = news_item if has_article_body else enrich_fda_news_item(news_item)

    if not filter_fda_catalysts([enriched_item]):
        return None

    target = identify_fda_target(enriched_item, watchlist)
    if target is None:
        return None

    catalyst = build_fda_catalyst(enriched_item)
    catalyst["ticker"] = target.get("ticker")
    catalyst["company"] = target.get("company")
    catalyst["program"] = target.get("program")
    catalyst["match_type"] = target.get("match_type")
    catalyst["match_confidence"] = target.get("confidence")
    catalyst["company_matches"] = target.get("company_matches", [])
    catalyst["program_matches"] = target.get("program_matches", [])

    scored = score_fda_event(catalyst)
    trading = enrich_trading_event(scored)
    trading = enrich_alert_priority(trading)
    trading["pipeline"] = "FDA_NEWS"
    # Preserve the established pipeline contract: the new priority is
    # an enrichment field, not a replacement for the Trading Intelligence stage.
    trading["pipeline_stage"] = "TRADING_INTELLIGENCE"
    return trading


def process_fda_news(news_items, watchlist=None):
    """Processa una lista di FDA News Items."""
    if not news_items:
        return []
    results = []
    for news_item in news_items:
        result = process_fda_news_item(news_item, watchlist)
        if result is not None:
            results.append(result)
    return results


def filter_fda_trading_alerts(events):
    """Restituisce gli eventi FDA con impatto significativo."""
    if not events:
        return []
    return [
        event for event in events
        if event.get("trading_impact") in {"EXTREME", "HIGH"}
    ]


def sort_fda_events(events):
    """Ordina gli eventi FDA per priorità operativa unificata."""
    return sort_by_alert_priority(events)


def get_top_fda_events(events, limit=10):
    """Restituisce i migliori eventi FDA secondo la priorità operativa."""
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 10
    if limit <= 0:
        return []
    return sort_fda_events(events)[:limit]
