from __future__ import annotations

from src.engine.diagram_semantic_builder import build_diagram_semantic_graph


def test_build_diagram_semantic_graph_groups_edges_and_states() -> None:
    transitions = [
        {
            "id": "SM_D_001",
            "from_state": "NORMAL",
            "to_state": "SHUT_OFF",
            "event": "diagram_transition",
            "raw_condition": "NORMAL -> SHUT_OFF",
            "source": {"file": "diagram.png", "kind": "diagram_image_ocr", "page": 1},
            "confidence": "medium",
            "review_required": True,
            "derivation": "diagram_text",
        },
        {
            "id": "SM_D_002",
            "from_state": "NORMAL",
            "to_state": "SHUT_OFF",
            "event": "diagram_transition",
            "raw_condition": "NORMAL -> SHUT_OFF",
            "source": {"file": "spec.docx", "kind": "diagram_narrative", "paragraph": 12},
            "confidence": "low",
            "review_required": True,
            "derivation": "diagram_text",
        },
        {
            "id": "SM_D_003",
            "from_state": "NORMAL",
            "to_state": "RESET",
            "event": "FORCE_RESET",
            "raw_condition": "FORCE_RESET = TRUE",
            "source": {"file": "diagram.png", "kind": "diagram_image_ocr"},
            "confidence": "medium",
            "review_required": True,
            "derivation": "diagram_state_rule",
        },
    ]
    diagrams = [
        {
            "file": "/tmp/diagram.png",
            "name": "diagram.png",
            "ocr_text": "STATE: NORMAL\nSTATE: SHUT OFF\nNORMAL -> SHUT_OFF",
            "source_kind": "diagram_image_ocr",
        }
    ]
    state_rules = [
        {"name": "FORCE_RESET", "expression": "TRUE", "source": {"file": "diagram.png", "kind": "state_rule"}}
    ]

    graph = build_diagram_semantic_graph(transitions=transitions, diagrams=diagrams, state_rules=state_rules)

    assert graph["graph_built"] is True
    assert graph["summary"]["states_total"] >= 3
    assert graph["summary"]["edges_total"] == 2
    assert graph["summary"]["explicit_edges"] == 1
    assert graph["summary"]["rule_inferred_edges"] == 1
    normal_node = next(row for row in graph["states"] if row["state"] == "NORMAL")
    assert normal_node["ocr_mentioned"] is True
    shut_off_edge = next(row for row in graph["edges"] if row["to_state"] == "SHUT_OFF")
    assert shut_off_edge["semantic_type"] == "explicit_arrow"
    assert len(shut_off_edge["transition_ids"]) == 2
