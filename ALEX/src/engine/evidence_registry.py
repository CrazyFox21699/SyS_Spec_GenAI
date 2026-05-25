"""Build and merge the evidence registry for a analyze job."""

from __future__ import annotations

from typing import Any

from src.models.evidence_model import make_evidence_ref


def _index_by_id(refs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r["id"]): r for r in refs if r.get("id")}


def build_evidence_registry(
    *,
    merged_cell_evidence: list[dict[str, Any]] | None = None,
    footnote_definitions: list[dict[str, Any]] | None = None,
    alias_map: list[dict[str, Any]] | None = None,
    logic_blocks: list[dict[str, Any]] | None = None,
    condition_definitions: list[dict[str, Any]] | None = None,
    diagram_meta: list[dict[str, Any]] | None = None,
    extra_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble evidence_registry section for ui_bundle.yaml."""
    refs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def add(ref: dict[str, Any]) -> None:
        rid = str(ref.get("id") or "")
        if not rid or rid in seen_ids:
            return
        seen_ids.add(rid)
        refs.append(ref)

    for ref in merged_cell_evidence or []:
        add(ref)

    for ref in extra_refs or []:
        add(ref)

    for foot in footnote_definitions or []:
        src = foot.get("source") if isinstance(foot.get("source"), dict) else {}
        file_name = str(src.get("file") or foot.get("file") or "")
        add(
            make_evidence_ref(
                kind="footnote",
                file=file_name,
                source=src,
                excerpt=str(foot.get("definition") or foot.get("raw_text") or foot.get("name") or ""),
                derives_from=[str(x) for x in (foot.get("derives_from") or []) if x],
                confidence="medium",
                review_required=True,
                linked_logic_ids=[str(foot["logic_id"])] if foot.get("logic_id") else [],
            )
        )

    for alias in alias_map or []:
        src = alias.get("source") if isinstance(alias.get("source"), dict) else {}
        file_name = str(src.get("file") or "")
        add(
            make_evidence_ref(
                kind="alias",
                file=file_name,
                source=src,
                excerpt=f"{alias.get('alias', '')} -> {alias.get('target', '')}",
                confidence="medium",
                review_required=True,
            )
        )

    for block in logic_blocks or []:
        src = block.get("source") if isinstance(block.get("source"), dict) else {}
        file_name = str(src.get("file") or "")
        if not file_name:
            continue
        add(
            make_evidence_ref(
                kind="table_cell",
                file=file_name,
                source=src,
                excerpt=str(block.get("raw_expression") or block.get("name") or "")[:500],
                confidence="high" if block.get("parse_status") == "ok" else "low",
                review_required=block.get("parse_status") != "ok",
                linked_logic_ids=[str(block["id"])] if block.get("id") else [],
            )
        )

    for definition in condition_definitions or []:
        src = definition.get("source") if isinstance(definition.get("source"), dict) else {}
        file_name = str(src.get("file") or "")
        if not file_name:
            continue
        add(
            make_evidence_ref(
                kind="table_cell",
                file=file_name,
                source=src,
                excerpt=str(definition.get("definition") or definition.get("name") or "")[:500],
                confidence="medium",
                review_required=True,
                linked_logic_ids=[str(definition["logic_id"])] if definition.get("logic_id") else [],
            )
        )

    for meta in diagram_meta or []:
        file_name = str(meta.get("file") or meta.get("path") or "")
        if not file_name:
            continue
        kind = "image_ocr" if meta.get("ocr_text") or meta.get("ocr_snippets") else "pdf_region"
        excerpt = str(meta.get("ocr_text") or meta.get("caption") or meta.get("summary") or "")[:500]
        add(
            make_evidence_ref(
                kind=kind,
                file=file_name,
                source={"file": file_name},
                excerpt=excerpt,
                confidence="low",
                review_required=True,
            )
        )

    by_id = _index_by_id(refs)
    return {
        "version": "1",
        "total": len(refs),
        "items": refs,
        "by_id": by_id,
    }
