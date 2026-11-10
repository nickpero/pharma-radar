from scanner.sec_financial_analysis import analyze_sec_financial_filing


def test_detects_going_concern_as_critical():
    text = ("Management concluded that there is substantial doubt about the company's "
            "ability to continue as a going concern. " * 8)
    result = analyze_sec_financial_filing(text)
    assert result["status"] == "ANALYZED"
    assert result["alert_level"] == "CRITICAL"
    assert "GOING_CONCERN" in {item["code"] for item in result["signals"]}


def test_detects_debt_default_as_critical():
    text = ("The company was in an event of default under its credit agreement. " * 8)
    result = analyze_sec_financial_filing(text)
    assert result["alert_level"] == "CRITICAL"
    assert "DEFAULT_OR_COVENANT" in {item["code"] for item in result["signals"]}


def test_detects_guidance_withdrawal_as_high():
    text = ("The company withdrew its full-year guidance following the quarter. " * 8)
    result = analyze_sec_financial_filing(text)
    assert result["alert_level"] == "HIGH"
    assert "GUIDANCE_WITHDRAWN" in {item["code"] for item in result["signals"]}


def test_no_signal_on_generic_financial_text():
    text = ("The company reported quarterly financial results and continues its operations. " * 8)
    result = analyze_sec_financial_filing(text)
    assert result["alert_level"] == "NONE"
    assert result["signals"] == []


def test_insufficient_text_is_not_interpreted():
    result = analyze_sec_financial_filing("Cash and debt.")
    assert result["status"] == "INSUFFICIENT_CONTENT"
    assert result["alert_level"] == "NONE"
