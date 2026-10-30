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
from scanner import ema_feed, early_discovery_feed, sec_feed


def _process_item(item, watchlist):
    # SEC and early-discovery records already carry an issuer ticker assigned
    # by their source adapter. Never let a coincidental drug/program alias
    # reassign that record to a different watchlist company.
    source = str(item.get("source") or "").strip().upper()
    source_ticker = str(item.get("ticker") or "").strip().upper()
    match_watchlist = watchlist
    if source in {"SEC", "EARLY_DISCOVERY"} and source_ticker in watchlist:
        match_watchlist = {source_ticker: watchlist[source_ticker]}

    # EMA article bodies may mention unrelated companies, indications, or
    # comparator drugs. For issuer/program attribution, use only the headline
    # and feed summary; keep the full article for event classification below.
    match_item = item
    if source == "EMA":
        match_item = {
            key: item.get(key)
            for key in ("source", "title", "summary", "description", "url", "published_at")
        }

    # SEC Form 8-K Item 2.02 is the issuer earnings/results disclosure.
    # It is intentionally company-level: quarterly results need not name a single
    # pipeline asset, but the SEC adapter has already bound the filing to its CIK/ticker.
    sec_items = {str(code).strip() for code in (item.get("filing_items") or [])}
    is_company_financial_results = (
        source == "SEC" and source_ticker in watchlist and "2.02" in sec_items
    )
    if is_company_financial_results:
        company_meta = watchlist[source_ticker]
        target = {
            "ticker": source_ticker,
            "company": company_meta.get("company", source_ticker),
            "program": None,
            "match_type": "COMPANY_LEVEL_SEC_ITEM_2_02",
            "confidence": "HIGH",
            "company_matches": [company_meta.get("company", source_ticker)],
            "program_matches": [],
        }
    else:
        target = identify_fda_target(match_item, match_watchlist)
    if target is None:
        return None
    # EMA headlines can mention disease areas or broad indications that overlap
    # weak program aliases. Require an explicit issuer match for attribution.
    if source == "EMA" and not target.get("company_matches"):
        return None
    if source in {"SEC", "EARLY_DISCOVERY"} and source_ticker in watchlist:
        if str(target.get("ticker") or "").strip().upper() != source_ticker:
            return None

    # EMA headlines often cover several medicines or generic committee business.
    # A program-name coincidence alone is insufficient: require the matched
    # company to be explicitly present in the official article as well.
    if source == "EMA":
        if not target.get("program_matches") or not target.get("company_matches"):
            return None

    event = build_fda_catalyst(item)
    if is_company_financial_results:
        event.update({
            "type": "CORPORATE_EVENT",
            "subtype": "COMPANY_FINANCIAL_RESULTS",
            "catalyst_type": "COMPANY_FINANCIAL_RESULTS",
            "severity": "MEDIUM",
            "direction": "UNKNOWN",
            "urgency": "MEDIUM",
        })
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
    if is_company_financial_results:
        # Keep earnings announcements visible as informational WATCH alerts;
        # do not imply that headline results are positive or negative.
        trading["subtype"] = "COMPANY_FINANCIAL_RESULTS"
        trading["trading_impact"] = "MEDIUM"
        trading["direction"] = "UNKNOWN"
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
    ema_seen = 0
    ema_matched = 0
    for item in items or []:
        is_ema = str((item or {}).get("source") or "").strip().upper() == "EMA"
        if is_ema:
            ema_seen += 1
        event = _process_item(item, watchlist)
        if event is None:
            continue
        if is_ema:
            ema_matched += 1
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
    if ema_seen:
        print(
            f"EMA MATCH AUDIT: seen={ema_seen} matched={ema_matched} "
            f"rejected={ema_seen - ema_matched} match_scope=title_summary",
            flush=True,
        )
    return sort_by_alert_priority(results)


def scan_regulatory_sources(watchlist, ema_max=50, sec_per_company=3):
    early_news = get_early_news(watchlist)
    ema_news = get_ema_news(max_items=ema_max)
    sec_news = get_sec_news(watchlist, max_filings_per_company=sec_per_company)
    all_news = early_news + ema_news + sec_news
    events = process_regulatory_news(all_news, watchlist)
    source_diagnostics = {
        "EARLY_DISCOVERY": dict(early_discovery_feed.LAST_FETCH_STATUS),
        "EMA": dict(ema_feed.LAST_FETCH_STATUS),
        "SEC": dict(sec_feed.LAST_FETCH_STATUS),
    }
    print("REGULATORY SOURCE HEALTH: " + " | ".join(
        "{}={} items={}".format(name, detail.get("status", "UNKNOWN"), detail.get("count", 0))
        + (" error={}".format(detail.get("error")) if detail.get("error") else "")
        for name, detail in source_diagnostics.items()
    ), flush=True)
    return {
        "source_diagnostics": source_diagnostics,
        "early_news": early_news,
        "ema_news": ema_news,
        "sec_news": sec_news,
        "news": all_news,
        "events": events,
        # MEDIUM-impact events enter the final freshness/primary-source/priority
        # gate. This improves recall without making every medium event a Telegram alert.
        "alerts": [event for event in events if is_regulatory_alert_candidate(event)],
    }


def is_regulatory_alert_candidate(event):
    """Allow medium-impact matched events to reach the strict final delivery gate."""
    return str((event or {}).get("trading_impact") or "").upper() in {"EXTREME", "HIGH", "MEDIUM"}
