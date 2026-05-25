from __future__ import annotations

import pytest

from src.engine.document_graph_builder import (
    add_user_edge,
    build_document_graph,
    delete_user_edge,
    node_detail,
)


def _bundle_with_two_files() -> dict:
    return {
        "classified_files": [
            {"file": "/job/Power_Mode.docx", "role": "system_spec", "file_type": "system_spec"},
            {
                "file": "/job/Test_Power_State.xlsx",
                "role": "test_spec_reference",
                "file_type": "test_spec",
            },
            {"file": "/job/diagram.png", "role": "system_spec", "file_type": "system_spec"},
        ],
        "logic_blocks": [
            {
                "id": "LOGIC_001",
                "name": "SHUTOFF",
                "raw_expression": "A AND B",
                "source": {"file": "/job/Power_Mode.docx", "table_id": "t1"},
                "parse_status": "ok",
            }
        ],
        "footnote_definitions": [
            {
                "ref": "(*1)",
                "definition": "Refer to Test_Power_State_Spec sheet for details",
                "raw_text": "Refer to Test_Power_State_Spec sheet for details",
                "source": {"file": "/job/Power_Mode.docx", "paragraph": 12},
                "cross_refs": [
                    {"type": "sheet", "text": "Test_Power_State_Spec", "resolved_node": None}
                ],
            }
        ],
        "alias_map": [
            {
                "alias": "SHUTOFF",
                "target": "OK_SHUTOFF",
                "raw_text": "SHUTOFF refer to Test_Power_State.xlsx",
                "source": {"file": "/job/Power_Mode.docx", "row": 4},
            }
        ],
        "two_column_tables": [
            {
                "source": {
                    "file": "/job/Test_Power_State.xlsx",
                    "sheet": "Test_Power_State_Spec",
                    "row": 1,
                }
            }
        ],
        "transitions": [
            {
                "id": "TR_001",
                "from_state": "S1",
                "to_state": "S2",
                "event": "evt",
                "diagram_link": "diagram.png",
                "source": {"file": "/job/Power_Mode.docx", "row": 8},
            }
        ],
        "diagrams": [
            {"file": "/job/diagram.png", "kind": "diagram", "ocr_text": "S1 -> S2"}
        ],
        "code_references": [],
        "condition_definitions": [],
    }


def test_build_document_graph_creates_node_per_classified_file():
    bundle = _bundle_with_two_files()
    graph = build_document_graph(bundle)

    assert graph["summary"]["node_count"] == 3
    names = sorted(n["name"] for n in graph["nodes"])
    assert names == ["Power_Mode.docx", "Test_Power_State.xlsx", "diagram.png"]


def test_build_document_graph_emits_alias_and_test_derived_from_edges():
    bundle = _bundle_with_two_files()
    graph = build_document_graph(bundle)
    kinds = {edge["kind"] for edge in graph["edges"]}
    assert "alias" in kinds, "alias edge expected from cross-file alias raw_text"
    assert "test_derived_from" in kinds, "test spec → system spec edge expected"
    # The footnote refers to the Excel sheet name and resolves via sheet_index
    assert "footnote_ref" in kinds


def test_build_document_graph_emits_diagram_link_edge():
    bundle = _bundle_with_two_files()
    graph = build_document_graph(bundle)
    diagram_edges = [e for e in graph["edges"] if e["kind"] == "diagram_link"]
    assert diagram_edges, "diagram_link edge expected when transition.diagram_link matches a diagram file"


def test_build_document_graph_preserves_user_edges_across_rebuild():
    bundle = _bundle_with_two_files()
    graph = build_document_graph(bundle)
    src = graph["nodes"][0]["id"]
    tgt = graph["nodes"][1]["id"]
    add_user_edge(graph, source_id=src, target_id=tgt, label="engineer link", note="manual")

    bundle["document_graph"] = graph
    rebuilt = build_document_graph(bundle)
    user_edges = rebuilt["user_edges"]
    assert len(user_edges) == 1
    assert user_edges[0]["label"] == "engineer link"
    assert user_edges[0]["confidence"] == "user"


def test_add_user_edge_rejects_unknown_nodes_or_self_loops():
    bundle = _bundle_with_two_files()
    graph = build_document_graph(bundle)
    src = graph["nodes"][0]["id"]
    with pytest.raises(ValueError):
        add_user_edge(graph, source_id="DOC_DEADBEEF", target_id=src)
    with pytest.raises(ValueError):
        add_user_edge(graph, source_id=src, target_id=src)


def test_delete_user_edge_removes_only_user_edges():
    bundle = _bundle_with_two_files()
    graph = build_document_graph(bundle)
    src = graph["nodes"][0]["id"]
    tgt = graph["nodes"][1]["id"]
    edge = add_user_edge(graph, source_id=src, target_id=tgt, label="engineer link")
    delete_user_edge(graph, edge["id"])
    assert graph["user_edges"] == []
    with pytest.raises(KeyError):
        delete_user_edge(graph, "EDG_unknown")


def test_node_detail_returns_artifacts_for_selected_file():
    bundle = _bundle_with_two_files()
    graph = build_document_graph(bundle)
    docx_node = next(n for n in graph["nodes"] if n["name"] == "Power_Mode.docx")

    detail = node_detail(bundle, graph, docx_node["id"])

    assert detail["node"]["id"] == docx_node["id"]
    assert len(detail["logic_blocks"]) == 1
    assert detail["logic_blocks"][0]["name"] == "SHUTOFF"
    assert len(detail["footnotes"]) == 1
    assert detail["footnotes"][0]["ref"] == "(*1)"
    assert len(detail["transitions"]) == 1


def test_node_detail_raises_for_unknown_node():
    bundle = _bundle_with_two_files()
    graph = build_document_graph(bundle)
    with pytest.raises(KeyError):
        node_detail(bundle, graph, "DOC_UNKNOWN")
