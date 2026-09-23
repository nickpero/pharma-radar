from unittest.mock import patch

from scanner.catalyst_dedup import is_restatement, filter_known_catalysts


def _alert(
    ticker="RARE",
    program="UX111",
    subtype="FDA_APPROVAL",
    published="2026-09-23",
    content="On September 17, 2026, the FDA approved FAYUVI (UX111).",
):
    return {
        "ticker": ticker,
        "program": program,
        "subtype": subtype,
        "source": "SEC",
        "published_at": published,
        "title": f"SEC 8-K — {ticker}",
        "content": content,
        "event": {"subtype": subtype, "published_at": published},
    }


def test_same_approval_date_is_restatement():
    current = _alert()
    prior = _alert(published="2026-09-17")
    assert is_restatement(current, prior) is True


def test_material_new_indication_is_kept():
    current = _alert(
        content=(
            "On September 23, 2026, the FDA approved a new indication "
            "for FAYUVI (UX111). This expanded indication is material."
        )
    )
    prior = _alert(published="2026-09-17")
    assert is_restatement(current, prior) is False


def test_different_catalyst_date_is_kept():
    current = _alert(
        content="On September 23, 2026, the FDA approved UX111 for a new program."
    )
    prior = _alert(published="2026-09-17")
    assert is_restatement(current, prior) is False


def test_sec_restatement_can_be_suppressed_from_memory():
    current = _alert()
    prior = _alert(published="2026-09-17")
    with patch("scanner.catalyst_dedup.find_similar_events", return_value=[prior]):
        fresh, suppressed = filter_known_catalysts([current])
    assert fresh == []
    assert len(suppressed) == 1
    assert suppressed[0]["dedup_status"] == "RESTATEMENT_DUPLICATE"


def test_different_program_is_not_duplicate():
    current = _alert(program="GENGLYCOS")
    prior = _alert(program="UX111", published="2026-09-17")
    assert is_restatement(current, prior) is False


if __name__ == "__main__":
    test_same_approval_date_is_restatement()
    test_material_new_indication_is_kept()
    test_different_catalyst_date_is_kept()
    test_sec_restatement_can_be_suppressed_from_memory()
    test_different_program_is_not_duplicate()
    print("OK catalyst dedup tests")
