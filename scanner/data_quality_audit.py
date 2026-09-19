"""Pharma Radar — Data Quality Audit V1.0."""
from __future__ import annotations

def audit_alert(alert):
    issues=[]
    ticker=str(alert.get("ticker") or "").strip().upper()
    if not ticker: issues.append("ticker_missing")
    if alert.get("program") in (None,"","UNKNOWN","N/A"): issues.append("program_missing")
    if str(alert.get("direction") or "").upper()=="UNKNOWN": issues.append("direction_unknown")
    try:
        score=float(alert.get("score"))
        if not 0<=score<=100: issues.append("catalyst_score_out_of_range")
    except (TypeError,ValueError): issues.append("catalyst_score_missing")
    if not (alert.get("event_timestamp") or alert.get("published_at") or alert.get("timestamp")): issues.append("event_timestamp_missing")
    if not str(alert.get("source_type") or "").strip(): issues.append("source_missing")
    n,med,win=alert.get("historical_edge_sample"),alert.get("historical_edge_median_1d_pct"),alert.get("historical_edge_win_rate_1d")
    if n is None or med is None or win is None: issues.append("historical_edge_incomplete")
    else:
        try:
            if float(n)<0: issues.append("historical_sample_invalid")
            if not 0<=float(win)<=1: issues.append("historical_win_rate_invalid")
        except (TypeError,ValueError): issues.append("historical_edge_invalid")
    market=alert.get("market_data") or {}
    if not market: issues.append("market_data_missing")
    else:
        if market.get("price") is None: issues.append("market_price_missing")
        if market.get("price_change_pct") is None: issues.append("market_change_missing")
    reaction=alert.get("market_reaction") or {}
    if reaction.get("reaction_status")=="AVAILABLE":
        if reaction.get("event_price") is None: issues.append("intraday_event_price_missing")
        if not reaction.get("event_timestamp"): issues.append("intraday_event_timestamp_missing")
    if alert.get("trading_intelligence_score") is None: issues.append("ti_score_missing")
    return {"ticker":ticker or "UNKNOWN","issues":issues,"quality":"PASS" if not issues else "WARN"}

def audit_alerts(alerts):
    rows=[audit_alert(a) for a in (alerts or [])]
    warnings=sum(bool(r["issues"]) for r in rows)
    return {"version":"1.0","alerts":len(rows),"pass":len(rows)-warnings,"warnings":warnings,"status":"PASS" if warnings==0 else "WARN","rows":rows}
