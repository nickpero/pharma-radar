from scanner.data_quality_audit import audit_alert,audit_alerts

def test_complete_alert_passes():
    e={"ticker":"IONS","program":"zilganersen","direction":"CATALYST","score":100,"event_timestamp":"2026-09-19T15:00:00Z","source_type":"PRIMARY_REGULATORY","historical_edge_sample":13,"historical_edge_median_1d_pct":1.3,"historical_edge_win_rate_1d":0.67,"market_data":{"price":20,"price_change_pct":-4.9},"market_reaction":{"reaction_status":"UNAVAILABLE"},"trading_intelligence_score":70}
    assert audit_alert(e)["quality"]=="PASS"

def test_invalid_fields_warn():
    r=audit_alert({"ticker":"IONS","score":120,"direction":"UNKNOWN"})
    assert "catalyst_score_out_of_range" in r["issues"]
    assert "event_timestamp_missing" in r["issues"]

def test_summary():
    r=audit_alerts([{"ticker":"IONS","score":100,"direction":"POSITIVE","program":"x"}])
    assert r["status"]=="WARN" and r["warnings"]==1
