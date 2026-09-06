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

Il modulo NON invia Telegram.
La notifica verrà collegata successivamente
al livello principale del Radar.
"""

from scanner.fda_news import (
    filter_fda_catalysts,
)

from scanner.fda_enrichment import (
    enrich_fda_news_item,
)

from scanner.fda_matcher import (
    identify_fda_target,
)

from scanner.fda_catalyst import (
    build_fda_catalyst,
)

from scanner.fda_score import (
    score_fda_event,
)

from scanner.trading_intelligence import (
    enrich_trading_event,
)


# ============================================
# PROCESS SINGLE FDA NEWS
# ============================================

def process_fda_news_item(
    news_item,
    watchlist=None,
):
    """
    Processa una singola FDA News Item.

    Flusso:

    FDA News
        ↓
    Article Enrichment
        ↓
    Catalyst relevance
        ↓
    Watchlist matching
        ↓
    Catalyst Event
        ↓
    FDA Score
        ↓
    Trading Intelligence

    Restituisce None se la news non è
    rilevante oppure non trova un target
    nella watchlist.
    """

    if not isinstance(
        news_item,
        dict,
    ):
        raise TypeError(
            "news_item must be a dictionary"
        )

    # ========================================
    # ARTICLE ENRICHMENT
    # ========================================

    enriched_item = enrich_fda_news_item(
        news_item
    )

    # ========================================
    # FDA RELEVANCE
    # ========================================

    relevant_news = filter_fda_catalysts(
        [enriched_item]
    )

    if not relevant_news:
        return None

    # ========================================
    # WATCHLIST MATCH
    # ========================================

    target = identify_fda_target(
        enriched_item,
        watchlist,
    )

    if target is None:
        return None

    # ========================================
    # BUILD CATALYST
    # ========================================

    catalyst = build_fda_catalyst(
        enriched_item
    )

    # ========================================
    # ATTACH TARGET
    # ========================================

    catalyst["ticker"] = target.get(
        "ticker"
    )

    catalyst["company"] = target.get(
        "company"
    )

    catalyst["program"] = target.get(
        "program"
    )

    catalyst["match_type"] = target.get(
        "match_type"
    )

    catalyst["match_confidence"] = target.get(
        "confidence"
    )

    catalyst["company_matches"] = target.get(
        "company_matches",
        []
    )

    catalyst["program_matches"] = target.get(
        "program_matches",
        []
    )

    # ========================================
    # FDA SCORE
    # ========================================

    scored = score_fda_event(
        catalyst
    )

    # ========================================
    # TRADING INTELLIGENCE
    # ========================================

    trading = enrich_trading_event(
        scored
    )

    # ========================================
    # PIPELINE METADATA
    # ========================================

    trading["pipeline"] = (
        "FDA_NEWS"
    )

    trading["pipeline_stage"] = (
        "TRADING_INTELLIGENCE"
    )

    return trading


# ============================================
# PROCESS MULTIPLE NEWS
# ============================================

def process_fda_news(
    news_items,
    watchlist=None,
):
    """
    Processa una lista di FDA News Items.

    Le news non rilevanti o senza match
    vengono escluse.
    """

    if not news_items:
        return []

    results = []

    for news_item in news_items:

        result = process_fda_news_item(
            news_item,
            watchlist,
        )

        if result is not None:

            results.append(
                result
            )

    return results


# ============================================
# FILTER BY TRADING IMPACT
# ============================================

def filter_fda_trading_alerts(
    events,
):
    """
    Restituisce soltanto gli eventi FDA
    con impatto Trading significativo.

    EXTREME e HIGH vengono mantenuti.
    """

    if not events:
        return []

    return [
        event
        for event in events
        if event.get(
            "trading_impact"
        ) in {
            "EXTREME",
            "HIGH",
        }
    ]


# ============================================
# SORT BY PRIORITY
# ============================================

def sort_fda_events(
    events,
):
    """
    Ordina gli eventi FDA dal più importante
    al meno importante.

    Priorità:
        EXTREME > HIGH > MEDIUM > LOW
    """

    priority = {
        "EXTREME": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    return sorted(
        events or [],
        key=lambda event: priority.get(
            event.get(
                "trading_impact",
                "LOW",
            ),
            0,
        ),
        reverse=True,
    )


# ============================================
# TOP FDA EVENTS
# ============================================

def get_top_fda_events(
    events,
    limit=10,
):
    """
    Restituisce i migliori eventi FDA
    secondo l'impatto Trading.

    Il limite predefinito è 10.
    """

    try:
        limit = int(limit)
    except (
        ValueError,
        TypeError,
    ):
        limit = 10

    if limit <= 0:
        return []

    ordered = sort_fda_events(
        events
    )

    return ordered[:limit]
