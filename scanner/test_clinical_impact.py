from scanner.clinical_impact import enrich_clinical_impact

def test_vktx_maintenance_data():
    event = {"type":"FDA_EVENT","subtype":"CLINICAL_RESULTS","severity":"HIGH","direction":"POSITIVE",
             "title":"Viking reports positive topline results from VK2735 maintenance study",
             "summary":"Patients maintained weight loss with every two weeks and monthly dosing."}
    result = enrich_clinical_impact(event)
    assert result["catalyst_category"] == "CLINICAL_DATA_RELEASE"
    assert result["subtype"] in {"MAINTENANCE_DATA", "TOPLINE_RESULTS"}
    assert result["novelty_score"] > 0
    assert result["market_impact_score"] >= 75

def test_primary_endpoint_failure():
    event = {"type":"FDA_EVENT","subtype":"CLINICAL_RESULTS","severity":"HIGH","direction":"NEGATIVE",
             "title":"Phase 3 study failed to meet the primary endpoint"}
    result = enrich_clinical_impact(event)
    assert result["subtype"] == "PRIMARY_ENDPOINT_FAILED"
    assert result["market_impact_score"] >= 80

def test_non_clinical_event():
    result = enrich_clinical_impact({"type":"FDA_EVENT","subtype":"FDA_APPROVAL","title":"FDA approves therapy"})
    assert result["market_impact_score"] == 0
