from src.engine.concrete_test_values import materialize_expected_input


def test_materialize_dedupes_same_signal() -> None:
    candidate = {
        "traceability": {"logic_block": "LB1"},
        "operation": {
            "given": [
                {"signal": "OK_SHUTOFF", "value": "1", "operator": "=="},
                {"signal": "OK_SHUTOFF", "value": "10", "operator": "=="},
            ]
        },
    }
    text = materialize_expected_input(candidate, definition_lookup={"OK_SHUTOFF": [{"definition": "= 1"}]})
    assert "OK_SHUTOFF=1" not in text or text.count("OK_SHUTOFF") == 1
    assert "OK_SHUTOFF=10" in text
