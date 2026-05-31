#!/usr/bin/env python3
"""Walk through spec→code MVP locally (no server, no LLM). Run: python scripts/demo_spec_to_code_mvp.py"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import textwrap

from src.parsers.code_parser import index_alex_blocks
from web.code_text_transform import import_monolith_to_drafts, merge_drafts_to_monolith
from web.gtest_workspace import (
    bulk_regen_comments,
    classify_sync_status,
    generate_draft_for_request,
    save_draft,
)


def hr(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def show_sync(bundle: dict, state: dict) -> None:
    sync = classify_sync_status(bundle, state)
    s = sync["summary"]
    print(
        f"  ok={s.get('ok', 0)}  no_code={s.get('no_code', 0)}  "
        f"stale_comment={s.get('stale_comment', 0)}  stale_body={s.get('stale_body', 0)}  "
        f"orphan={s.get('orphan_code', 0)}"
    )
    for row in sync["rows"]:
        print(f"    {row['candidate_id']:12} → {row['status']}")


def main() -> None:
    bundle = {
        "test_candidates": [
            {
                "id": "TC_PM_001",
                "event": "Shutdown",
                "operation": {
                    "given": [{"signal": "IGN_SW", "value": "0"}],
                    "when": [{"timing": "elapsed_time >= 50 ms"}],
                },
                "expectation": [{"signal": "Mode_STS", "value": "0"}],
                "traceability": {},
            },
            {
                "id": "TC_PM_008",
                "event": "Shutoff",
                "operation": {
                    "given": [{"signal": "RELAY_MAIN", "value": "ON"}],
                    "when": [{"timing": "elapsed_time >= 100 ms"}],
                },
                "expectation": [{"signal": "RELAY_MAIN", "value": "OFF"}],
                "traceability": {},
            },
        ],
        "logic_blocks": [],
        "signals": [],
        "ai_assists": {"candidate_overlays": {}},
    }
    gtest_state = {
        "harness": {"fixture_class": "PowerModeFixture"},
        "code_variable_map": {
            "IGN_SW": "in.IGN_SW",
            "Mode_STS": "out.Mode_STS",
            "RELAY_MAIN": "in.RELAY_MAIN",
        },
        "drafts": {},
        "tc_code_index": {},
    }

    hr("Bước 1 — Generate draft cho TC_PM_001 (template, không LLM)")
    draft = generate_draft_for_request(bundle, gtest_state, candidate_id="TC_PM_001")
    print(textwrap.indent(draft["full_snippet"][:320] + "...", "  "))
    gtest_state = save_draft(gtest_state, draft_key="TC_PM_001", draft=draft)
    print("\n  save_draft() tự thêm markers @alex:begin/end:")
    print(textwrap.indent(gtest_state["drafts"]["TC_PM_001"]["full_snippet"][:400] + "...", "  "))

    hr("Bước 2 — Sync status (1 TC có code, 1 TC chưa có)")
    show_sync(bundle, gtest_state)

    hr("Bước 3 — Giả lập spec đổi comment (stale_comment)")
    saved = dict(gtest_state["drafts"]["TC_PM_001"])
    from web.gtest_workspace import _structured_io_for_candidate

    structured = _structured_io_for_candidate(bundle, "TC_PM_001")
    from src.importers.customer_testspec_importer import compute_body_hash, compute_spec_hash

    saved["body_hash"] = compute_body_hash(structured)
    saved["spec_hash"] = "old_wrong_hash"
    gtest_state["drafts"]["TC_PM_001"] = saved
    show_sync(bundle, gtest_state)
    print("\n  → stale_comment = I/O (body_hash) khớp, comment/spec_hash lệch → regen comment an toàn")

    hr("Bước 4 — Bulk regen comment (giữ TEST_F body)")
    body_before = gtest_state["drafts"]["TC_PM_001"]["code_body"]
    bulk_regen_comments(bundle, gtest_state, ["TC_PM_001"])
    body_after = gtest_state["drafts"]["TC_PM_001"]["code_body"]
    print(f"  code_body unchanged: {body_before == body_after}")
    show_sync(bundle, gtest_state)

    hr("Bước 5 — Export monolith marked (2 TC)")
    draft2 = generate_draft_for_request(bundle, gtest_state, candidate_id="TC_PM_008")
    gtest_state = save_draft(gtest_state, draft_key="TC_PM_008", draft=draft2)
    monolith = merge_drafts_to_monolith(gtest_state, bundle)
    blocks = index_alex_blocks(monolith)
    print(f"  {len(blocks)} blocks indexed, {len(monolith.splitlines())} lines total")
    print(textwrap.indent(monolith[:500] + "\n  ...", "  "))

    hr("Bước 6 — Import monolith 8K-line style (parse local, không gửi LLM)")
    fresh = {"drafts": {}, "tc_code_index": {}, "harness": gtest_state["harness"]}
    out = import_monolith_to_drafts(fresh, monolith)
    print(f"  imported {out['count']} drafts: {out['imported']}")
    for cid, idx in fresh["tc_code_index"].items():
        print(f"    {cid}: lines {idx['line_start']}-{idx['line_end']}")

    hr("Tóm tắt — bạn làm gì trên UI")
    print(
        textwrap.dedent(
            """
            1. Import TestSpec → mỗi row có spec_hash/body_hash
            2. Tab Test Code → Generate / Save → draft có @alex markers
            3. Panel "Code Store" → Refresh sync → xem stale_comment / stale_body
            4. Regen comments (stale) → chỉ sửa comment, giữ TEST_F { ... }
            5. Export marked .cpp → file merge-friendly cho repo
            6. Import monolith → kéo file .cpp cũ vào → split theo marker → drafts

            Chạy UI: cd ALEX && ./dev.sh → mở http://localhost:8000 (hoặc port trong config.local.yaml)
            """
        ).strip()
    )


if __name__ == "__main__":
    main()
