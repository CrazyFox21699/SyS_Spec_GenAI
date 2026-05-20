from __future__ import annotations

from pathlib import Path

import pytest

from src.library import (
    add_item,
    add_link,
    delete_item,
    delete_link,
    import_dropped_file,
    load_library,
    save_library,
    scan_folder_listing,
    set_focus,
    set_root,
    update_item,
    update_link,
    validate_inside_root,
)


def _seed_root(tmp_path: Path) -> Path:
    root = tmp_path / "library_root"
    root.mkdir()
    (root / "Power_Mode.docx").write_text("placeholder", encoding="utf-8")
    (root / "Test_Power_State.xlsx").write_text("placeholder", encoding="utf-8")
    sub = root / "diagrams"
    sub.mkdir()
    (sub / "state_machine.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return root


# ----- root / browse / validate -------------------------------------------------


def test_load_library_returns_empty_state(tmp_path: Path) -> None:
    state = load_library(tmp_path)
    assert state["version"] == "3"
    assert state["root"] == ""
    assert state["focus_id"] == ""
    assert state["items"] == []
    assert state["links"] == []


def test_set_root_persists_and_drops_legacy_keys(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    save_library(tmp_path, state)
    reloaded = load_library(tmp_path)
    assert Path(reloaded["root"]).resolve() == root.resolve()


def test_scan_folder_listing_returns_files_under_root(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    listing = scan_folder_listing(state)
    names = {f["name"] for f in listing["files"]}
    assert "Power_Mode.docx" in names
    assert "Test_Power_State.xlsx" in names
    assert [d["name"] for d in listing["dirs"]] == ["diagrams"]


def test_validate_inside_root_blocks_outsiders(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    outside = tmp_path / "outside.docx"
    outside.write_text("x", encoding="utf-8")
    state = load_library(tmp_path)
    set_root(state, str(root))
    with pytest.raises(ValueError):
        validate_inside_root(state, str(outside))


# ----- items / focus / links ----------------------------------------------------


def test_add_item_promotes_first_to_focus(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    item = add_item(state)
    assert state["focus_id"] == item["id"]
    assert item["file"] == ""


def test_add_item_validates_supplied_file(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    item = add_item(state, file_path=str(root / "Power_Mode.docx"))
    assert item["file"].endswith("Power_Mode.docx")
    outside = tmp_path / "outside.docx"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        add_item(state, file_path=str(outside))


def test_update_item_clears_or_replaces_file(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    item = add_item(state)
    update_item(state, item["id"], file_path=str(root / "Power_Mode.docx"))
    assert state["items"][0]["file"].endswith("Power_Mode.docx")
    update_item(state, item["id"], file_path="")
    assert state["items"][0]["file"] == ""


def test_delete_item_removes_focus_and_links(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    focus = add_item(state)
    spoke = add_item(state)
    add_link(state, source_id=focus["id"], target_id=spoke["id"], label="Satisfies")
    removed = delete_item(state, focus["id"])
    assert removed == 1
    assert all(it["id"] != focus["id"] for it in state["items"])
    assert state["links"] == []
    assert state["focus_id"] == spoke["id"]


def test_add_link_auto_creates_target_when_missing(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    focus = add_item(state)
    link = add_link(state, source_id=focus["id"], target_id=None, label="Validated By")
    assert link["source"] == focus["id"]
    assert link["target"] != focus["id"]
    assert any(it["id"] == link["target"] for it in state["items"])
    assert link["label"] == "Validated By"


def test_add_link_rejects_self_loops(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    focus = add_item(state)
    with pytest.raises(ValueError):
        add_link(state, source_id=focus["id"], target_id=focus["id"], label="Same")


def test_update_link_label_falls_back_to_default_when_empty(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    focus = add_item(state)
    link = add_link(state, source_id=focus["id"], target_id=None, label="Satisfies")
    updated = update_link(state, link["id"], label="")
    assert updated["label"] == "References"
    update_link(state, link["id"], label="Implements")
    assert state["links"][0]["label"] == "Implements"


def test_delete_link_collapses_orphan_target(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    focus = add_item(state)
    link = add_link(state, source_id=focus["id"], target_id=None, label="Satisfies")
    target_id = link["target"]
    result = delete_link(state, link["id"])
    assert result["removed_item"] == target_id
    assert all(it["id"] != target_id for it in state["items"])
    assert state["focus_id"] == focus["id"]


def test_delete_link_keeps_target_when_other_links_remain(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    focus = add_item(state)
    link1 = add_link(state, source_id=focus["id"], target_id=None, label="Satisfies")
    add_link(state, source_id=focus["id"], target_id=link1["target"], label="Validated By")
    delete_link(state, link1["id"])
    assert any(it["id"] == link1["target"] for it in state["items"])
    assert state["links"][0]["label"] == "Validated By"


def test_set_focus_validates_existing_item(tmp_path: Path) -> None:
    state = load_library(tmp_path)
    with pytest.raises(KeyError):
        set_focus(state, "LIB_missing")


# ----- upload helper -----------------------------------------------------------


def test_import_dropped_file_copies_into_root(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    drop = tmp_path / "incoming.docx"
    drop.write_text("hello", encoding="utf-8")
    dest = import_dropped_file(state, drop, original_name="incoming.docx")
    assert dest.parent == root.resolve()
    assert dest.read_text(encoding="utf-8") == "hello"


def test_import_dropped_file_deduplicates_collisions(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    drop = tmp_path / "incoming.docx"
    drop.write_text("v1", encoding="utf-8")
    first = import_dropped_file(state, drop, original_name="Power_Mode.docx")
    second = import_dropped_file(state, drop, original_name="Power_Mode.docx")
    assert first != second
    assert first.parent == root.resolve()
    assert second.parent == root.resolve()


def test_import_dropped_file_requires_root(tmp_path: Path) -> None:
    state = load_library(tmp_path)
    drop = tmp_path / "incoming.docx"
    drop.write_text("v1", encoding="utf-8")
    with pytest.raises(ValueError):
        import_dropped_file(state, drop, original_name="incoming.docx")


def test_save_and_load_round_trip_preserves_items_and_links(tmp_path: Path) -> None:
    root = _seed_root(tmp_path)
    state = load_library(tmp_path)
    set_root(state, str(root))
    focus = add_item(state, file_path=str(root / "Power_Mode.docx"))
    link = add_link(state, source_id=focus["id"], target_id=None, label="Satisfies")
    save_library(tmp_path, state)
    reloaded = load_library(tmp_path)
    assert reloaded["focus_id"] == focus["id"]
    assert any(it["id"] == focus["id"] for it in reloaded["items"])
    assert any(l["id"] == link["id"] and l["label"] == "Satisfies" for l in reloaded["links"])
