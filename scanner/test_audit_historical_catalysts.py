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
    import json
    path.write_text(json.dumps(dataset), encoding="utf-8")
    monkeypatch.setattr(module, "DATASET", path)
    monkeypatch.setattr(module, "OUTPUT", tmp_path / "audit.json")
    result = audit()
    assert result["summary"]["direction_mismatches"] == 0
    assert result["summary"]["win_rate_directional"]["1D"] == 1.0


def test_dataset_builder_matches_edge_without_explicit_event_id(tmp_path, monkeypatch):
    import json
    import scanner.build_historical_catalyst_dataset as module

    event = {
        "ticker": "TEST",
        "program": "drug",
        "subtype": "FDA_APPROVAL",
        "event_timestamp": "2025-01-01",
        "source": "FDA",
        "url": "https://example.test/event",
        "direction": "POSITIVE",
    }
    edge_event = {
        **event,
        "event_id": "",
        "event_price": 100.0,
        "windows": {
            "1D": {"directional_abnormal_return_pct": 5.0},
            "3D": {"directional_abnormal_return_pct": 6.0},
            "5D": {"directional_abnormal_return_pct": 7.0},
        },
    }
    discovered_path = tmp_path / "discovered.json"
    edge_path = tmp_path / "edge.json"
    output_path = tmp_path / "dataset.json"
    discovered_path.write_text(json.dumps({"events": [event]}), encoding="utf-8")
    edge_path.write_text(json.dumps({"events": [edge_event]}), encoding="utf-8")
    monkeypatch.setattr(module, "DISCOVERED", discovered_path)
    monkeypatch.setattr(module, "EDGE", edge_path)
    monkeypatch.setattr(module, "OUTPUT", output_path)

    payload = module.build()
    assert payload["counts"]["tradable"] == 1
    assert payload["counts"]["tradable_with_market_metrics"] == 1
    assert payload["tradable_catalysts"][0]["market_metrics"]["event_price"] == 100.0


if __name__ == "__main__":
    print("Run with pytest or the GitHub Actions workflow.")
