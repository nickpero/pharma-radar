from scanner.daily_top5 import build_daily_top5, format_daily_top5


def snapshot(pct, volume_ratio=1.0):
    return {
        "price": 10.0,
        "price_change_pct": pct,
        "volume": 1000,
        "volume_ratio": volume_ratio,
        "market_data_source": "TEST",
    }


def test_top5_ranks_gainers_and_limits_to_five():
    watchlist = {
        f"T{i}": {"company": f"Company {i}", "programs": []}
        for i in range(7)
    }
    values = {f"T{i}": snapshot(i) for i in range(7)}
    rows = build_daily_top5(
        watchlist=watchlist,
        history={},
        snapshot_fn=lambda ticker: values[ticker],
        date_value="2026-09-29",
    )
    assert [row["ticker"] for row in rows] == ["T6", "T5", "T4", "T3", "T2"]


def test_same_day_catalyst_is_linked():
    watchlist = {"SMMT": {"company": "Summit Therapeutics", "programs": ["ivonescimab"]}}
    history = {
        "x": {
            "ticker": "SMMT",
            "event_timestamp": "2026-09-29",
            "subtype": "COMMERCIAL_PARTNERSHIP",
            "program": "ivonescimab",
            "source": "SEC",
            "alert_priority": 100,
        }
    }
    rows = build_daily_top5(
        watchlist=watchlist,
        history=history,
        snapshot_fn=lambda ticker: snapshot(22.0, 4.5),
        date_value="2026-09-29",
    )
    assert rows[0]["catalyst_found"] is True
    assert rows[0]["catalyst_subtype"] == "COMMERCIAL_PARTNERSHIP"
    assert rows[0]["classification"] == "CATALYST_LINKED"


def test_unexplained_move_is_not_called_a_catalyst():
    rows = build_daily_top5(
        watchlist={"ABC": {"company": "ABC Pharma", "programs": []}},
        history={},
        snapshot_fn=lambda ticker: snapshot(35.0, 6.0),
        date_value="2026-09-29",
    )
    assert rows[0]["classification"] == "MARKET_MOVE_UNEXPLAINED"
    assert rows[0]["catalyst_evidence"] == "NO_VERIFIED_SAME_DAY_CATALYST"


def test_format():
    message = format_daily_top5([
        {
            "ticker": "SMMT",
            "company": "Summit Therapeutics",
            "price_change_pct": 22.0,
            "volume_ratio": 4.5,
            "catalyst_found": True,
            "catalyst_subtype": "COMMERCIAL_PARTNERSHIP",
            "catalyst_source": "SEC",
        }
    ], "2026-09-29")
    assert "DAILY TOP 5" in message
    assert "SMMT" in message
    assert "+22.00%" in message
    assert "CATALYST LINKED" in message


if __name__ == "__main__":
    test_top5_ranks_gainers_and_limits_to_five()
    test_same_day_catalyst_is_linked()
    test_unexplained_move_is_not_called_a_catalyst()
    test_format()
    print("Daily Top 5 tests passed")


def test_fundamental_catalyst_is_classified_separately():
    watchlist = {"CNTB": {"company": "Connect Biopharma", "programs": ["rademikibart"]}}
    history = {"x": {"ticker": "CNTB", "event_timestamp": "2026-09-30T14:00:00+00:00",
                      "subtype": "TOPLINE_RESULTS", "program": "rademikibart",
                      "source": "SEC", "alert_priority": 100}}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(86.0, 8.0),
        date_value="2026-09-30",
    )
    assert rows[0]["classification"] == "FUNDAMENTAL_OR_CLINICAL_CATALYST"
    assert rows[0]["catalyst_evidence"] == "RADAR_RECORDED_EVENT"


def test_company_level_corporate_transaction_can_pass_without_program():
    watchlist = {"PCRX": {"company": "Pacira BioSciences", "programs": ["EXPAREL", "ZILRETTA"]}}
    history = {"x": {
        "ticker": "PCRX",
        "event_timestamp": "2026-10-08T15:00:00+00:00",
        "subtype": "CORPORATE_TRANSACTION",
        "program": None,
        "source": "SEC",
        "source_type": "PRIMARY_CORPORATE",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(44.0, 50.0),
        date_value="2026-10-08",
    )
    assert rows[0]["alert_quality_gate"]["eligible"] is True
    assert rows[0]["radar_inclusion"] == "INCLUDE_IF_MATERIAL"


def test_corporate_transaction_is_fundamental():
    assert _classify_row({"subtype": "CORPORATE_TRANSACTION"}) == "FUNDAMENTAL_OR_CLINICAL_CATALYST"


def test_ip_catalyst_is_fundamental():
    assert _classify_row({"subtype": "IP_CATALYST"}) == "FUNDAMENTAL_OR_CLINICAL_CATALYST"


def test_regulatory_patent_catalyst_is_fundamental():
    c = {"subtype": "PATENT_RULING", "source": "COURT", "ticker": "UTHR"}
    assert _classify_row(c) == "FUNDAMENTAL_OR_CLINICAL_CATALYST"

def test_clinical_milestone_is_watch():
    c = {"subtype": "CLINICAL_MILESTONE", "source": "COMPANY", "ticker": "LONA"}
    assert _classify_row(c) == "DEVELOPMENT_MILESTONE_WATCH"


def test_market_structure_move_is_separate_from_pharma_catalyst():
    meta = {"company": "Moderna", "radar_role": "MARKET_STRUCTURE_WATCH"}
    assert _classify_row(None, meta) == "TECHNICAL_OR_INDEX_FLOW"


def test_regulatory_watch_without_same_day_catalyst_is_not_falsely_alerted():
    meta = {"company": "GRAIL", "radar_role": "REGULATORY_CATALYST_WATCH"}
    assert _classify_row(None, meta) == "WATCHLIST_CONTEXT_NO_NEW_CATALYST"


def test_same_day_secondary_catalyst_is_quality_gated():
    watchlist = {"ABC": {"company": "ABC Pharma", "programs": []}}
    history = {"x": {
        "ticker": "ABC",
        "event_timestamp": "2026-09-29T12:00:00+00:00",
        "subtype": "FDA_APPROVAL",
        "program": "drug",
        "source": "REUTERS",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(20.0, 3.0),
        date_value="2026-09-29",
    )
    assert rows[0]["alert_quality_gate"]["eligible"] is False
    assert rows[0]["alert_quality_gate"]["reason"] == "PRIMARY_SOURCE_NOT_VERIFIED"


def test_same_day_primary_catalyst_passes_quality_gate():
    watchlist = {"ABC": {"company": "ABC Pharma", "programs": []}}
    history = {"x": {
        "ticker": "ABC",
        "event_timestamp": "2026-09-29T12:00:00+00:00",
        "subtype": "FDA_APPROVAL",
        "program": "drug",
        "source": "FDA",
        "source_type": "PRIMARY_REGULATORY",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(20.0, 3.0),
        date_value="2026-09-29",
    )
    assert rows[0]["alert_quality_gate"]["eligible"] is True


def test_24_72h_catalyst_is_reaction_continuation():
    watchlist = {"ABC": {"company": "ABC Pharma", "programs": []}}
    history = {"x": {
        "ticker": "ABC",
        "event_timestamp": "2026-09-28T12:00:00+00:00",
        "subtype": "FDA_APPROVAL",
        "program": "drug",
        "source": "FDA",
        "source_type": "PRIMARY_REGULATORY",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(20.0, 3.0),
        date_value="2026-09-29",
    )
    assert rows[0]["catalyst_freshness"] == "REACTION_24_72H"
    assert rows[0]["classification"] == "FUNDAMENTAL_OR_CLINICAL_CATALYST"
    assert rows[0]["alert_quality_gate"]["eligible"] is True


def test_missing_timestamp_is_quality_gated():
    watchlist = {"ABC": {"company": "ABC Pharma", "programs": []}}
    history = {"x": {
        "ticker": "ABC",
        "event_timestamp": None,
        "subtype": "FDA_APPROVAL",
        "program": "drug",
        "source": "FDA",
        "source_type": "PRIMARY_REGULATORY",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(20.0, 3.0),
        date_value="2026-09-29",
    )
    assert rows[0]["alert_quality_gate"]["eligible"] is False
    assert rows[0]["alert_quality_gate"]["reason"] == "EVENT_TIMESTAMP_MISSING"


def test_72h_window_links_prior_day_catalyst():
    watchlist = {"PCVX": {"company": "Vaxcyte", "programs": ["VAX-31"]}}
    history = {"x": {
        "ticker": "PCVX",
        "event_timestamp": "2026-10-04T14:00:00+00:00",
        "subtype": "TOPLINE_RESULTS",
        "program": "VAX-31",
        "source": "COMPANY IR",
        "source_type": "PRIMARY_CORPORATE",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(30.0, 10.0),
        date_value="2026-10-05",
    )
    assert rows[0]["catalyst_found"] is True
    assert rows[0]["catalyst_freshness"] == "REACTION_24_72H"
    assert rows[0]["catalyst_program"] == "VAX-31"


def test_catalyst_program_must_be_verified_for_quality_gate():
    watchlist = {"APUS": {"company": "Apimeds Pharmaceuticals US", "programs": ["Apitox", "LT-100"]}}
    history = {"x": {
        "ticker": "APUS",
        "event_timestamp": "2026-10-05T14:00:00+00:00",
        "subtype": "COMMERCIAL_PARTNERSHIP",
        "program": None,
        "source": "COMPANY IR",
        "source_type": "PRIMARY_CORPORATE",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(40.0, 20.0),
        date_value="2026-10-05",
    )
    assert rows[0]["alert_quality_gate"]["eligible"] is False
    assert rows[0]["alert_quality_gate"]["reason"] == "PROGRAM_NOT_VERIFIED"


def test_verified_program_catalyst_wins_over_later_unscoped_event():
    watchlist = {"PCVX": {"company": "Vaxcyte", "programs": ["VAX-31"]}}
    history = {
        "clinical": {
            "ticker": "PCVX",
            "event_timestamp": "2026-10-05T12:00:00+00:00",
            "subtype": "TOPLINE_RESULTS",
            "program": "VAX-31",
            "source": "COMPANY IR",
            "source_type": "PRIMARY_CORPORATE",
            "alert_priority": 100,
        },
        "financing": {
            "ticker": "PCVX",
            "event_timestamp": "2026-10-05T16:00:00+00:00",
            "subtype": "FINANCING",
            "program": None,
            "source": "SEC",
            "source_type": "PRIMARY_CORPORATE",
            "alert_priority": 100,
        },
    }
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(30.0, 10.0),
        date_value="2026-10-05",
    )
    assert rows[0]["catalyst_program"] == "VAX-31"
    assert rows[0]["classification"] == "FUNDAMENTAL_OR_CLINICAL_CATALYST"
    assert rows[0]["alert_quality_gate"]["eligible"] is True


def test_quality_gate_blocks_radar_inclusion_for_secondary_source():
    watchlist = {"ABC": {"company": "ABC Pharma", "programs": ["Drug A"]}}
    history = {"x": {
        "ticker": "ABC",
        "event_timestamp": "2026-09-29T12:00:00+00:00",
        "subtype": "FDA_APPROVAL",
        "program": "Drug A",
        "source": "REUTERS",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(20.0, 8.0),
        date_value="2026-09-29",
    )
    assert rows[0]["radar_inclusion"] == "NO_NEW_ALERT"
    assert "Quality Gate" in rows[0]["radar_reason"]


def test_primary_fundamental_catalyst_is_radar_candidate():
    watchlist = {"LPCN": {"company": "Lipocine", "programs": ["TLANDO", "LPCN 1154"]}}
    history = {"x": {
        "ticker": "LPCN",
        "event_timestamp": "2026-10-07T12:00:00+00:00",
        "subtype": "FDA_APPROVAL",
        "program": "TLANDO",
        "source": "COMPANY IR",
        "source_type": "PRIMARY_CORPORATE",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(5.95, 80.0),
        date_value="2026-10-07",
    )
    assert rows[0]["classification"] == "FUNDAMENTAL_OR_CLINICAL_CATALYST"
    assert rows[0]["radar_inclusion"] == "INCLUDE_IF_MATERIAL"
    assert rows[0]["catalyst_program"] == "TLANDO"


def test_timeline_change_is_watch_only_not_fundamental():
    watchlist = {"ABC": {"company": "ABC Pharma", "programs": ["Drug A"]}}
    history = {"x": {
        "ticker": "ABC",
        "event_timestamp": "2026-09-29T12:00:00+00:00",
        "subtype": "DATE_DELAYED",
        "program": "Drug A",
        "source": "CLINICALTRIALS",
        "source_type": "PRIMARY_TRIAL",
        "alert_priority": 75,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(12.0, 3.0),
        date_value="2026-09-29",
    )
    assert rows[0]["classification"] == "DEVELOPMENT_MILESTONE_WATCH"
    assert rows[0]["radar_inclusion"] == "WATCH_ONLY"


def test_unexplained_microcap_move_stays_out_of_radar():
    watchlist = {"SXTC": {"company": "China SXT Pharmaceuticals", "programs": []}}
    rows = build_daily_top5(
        watchlist=watchlist,
        history={},
        snapshot_fn=lambda ticker: snapshot(376.8, 50.0),
        date_value="2026-10-07",
    )
    assert rows[0]["classification"] == "MARKET_MOVE_UNEXPLAINED"
    assert rows[0]["radar_inclusion"] == "WATCH_UNEXPLAINED_MOVE"


def test_prior_day_fundamental_reaction_does_not_create_new_alert():
    watchlist = {"PCVX": {"company": "Vaxcyte", "programs": ["VAX-31"]}}
    history = {"x": {
        "ticker": "PCVX",
        "event_timestamp": "2026-10-05T14:00:00+00:00",
        "subtype": "TOPLINE_RESULTS",
        "program": "VAX-31",
        "source": "COMPANY IR",
        "source_type": "PRIMARY_CORPORATE",
        "alert_priority": 100,
    }}
    rows = build_daily_top5(
        watchlist=watchlist, history=history,
        snapshot_fn=lambda ticker: snapshot(-11.6, 4.5),
        date_value="2026-10-06",
    )
    assert rows[0]["catalyst_freshness"] == "REACTION_24_72H"
    assert rows[0]["radar_inclusion"] == "REACTION_ONLY_NO_NEW_ALERT"


def test_premarket_history_dict_is_read_and_marks_new_today():
    from datetime import datetime, timezone
    from scanner import premarket
    original = premarket._load
    try:
        premarket._load = lambda path, fallback: {"event1": {"ticker": "LPCN", "event_timestamp": "2026-10-07T12:00:00+00:00", "recorded_at": "2026-10-07T12:01:00+00:00", "subtype": "FDA_APPROVAL", "program": "TLANDO", "source": "COMPANY IR"}}
        rows = premarket.recent_catalysts(now=datetime(2026, 10, 7, 13, 0, tzinfo=timezone.utc))
        assert rows
        assert rows[0]["ticker"] == "LPCN"
        assert rows[0]["catalyst_origin"] == "EMERGED_TODAY"
    finally:
        premarket._load = original
