from scanner.audit_historical_catalysts import audit


def test_audit_empty_dataset_fails_cleanly(tmp_path, monkeypatch):
    import scanner.audit_historical_catalysts as module

    path = tmp_path / "historical_catalyst_dataset.json"
    path.write_text('{"tradable_catalysts": []}', encoding="utf-8")
    monkeypatch.setattr(module, "DATASET", path)
    monkeypatch.setattr(module, "OUTPUT", tmp_path / "audit.json")
    result = audit()
    assert result["summary"]["events"] == 0


def test_negative_direction_is_oriented_correctly(tmp_path, monkeypatch):
    import scanner.audit_historical_catalysts as module

    dataset = {
        "tradable_catalysts": [
            {
                "event_id": "x",
                "ticker": "TEST",
                "program": "drug",
                "subtype": "FDA_REJECTION",
                "direction": "NEGATIVE",
                "event_timestamp": "2025-01-01",
                "source": "FDA_CRL",
                "market_metrics": {
                    "volume_expansion": 3.0,
                    "windows": {
                        "1D": {"abnormal_return_pct": -10.0, "directional_abnormal_return_pct": 10.0},
                        "3D": {"abnormal_return_pct": -8.0, "directional_abnormal_return_pct": 8.0},
                        "5D": {"abnormal_return_pct": -6.0, "directional_abnormal_return_pct": 6.0},
                    },
                },
            }
        ]
    }
    path = tmp_path / "historical_catalyst_dataset.json"
    path.write_text(__import__("json").dumps(dataset), encoding="utf-8")
    monkeypatch.setattr(module, "DATASET", path)
    monkeypatch.setattr(module, "OUTPUT", tmp_path / "audit.json")
    result = audit()
    assert result["summary"]["direction_mismatches"] == 0
    assert result["summary"]["win_rate_directional"]["1D"] == 1.0


if __name__ == "__main__":
    test_audit_empty_dataset_fails_cleanly(__import__("tempfile").TemporaryDirectory(), None)
