"""State backing the Polarion-style trace canvas on Tab 4.

The Library is a tiny manual model:

* ``root`` is the local folder the engineer points the tool at. OS drag-drops
  are copied into this folder so file paths stay local.
* ``items`` are slots on the canvas. Each slot may have a file path attached
  or be empty (a placeholder waiting for a drop / pick).
* ``focus_id`` is the slot rendered in the centre. Every link must source
  from the focus item so we always render a focus + spokes diagram.
* ``links`` carry a free-form ``label`` (e.g. "Satisfies", "Validated By",
  "Implemented By"). Inverse labels are not stored — the UI shows the
  outgoing label verbatim.
"""

from __future__ import annotations

import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from src.utils.file_filters import is_ingestible_file
from src.utils.yaml_utils import dump_yaml, load_yaml


LIBRARY_FILE = "library.yaml"


def library_path(web_data: Path) -> Path:
    return web_data / LIBRARY_FILE


def _empty_state() -> dict[str, Any]:
    return {
        "version": "3",
        "root": "",
        "focus_id": "",
        "items": [],
        "links": [],
    }


def load_library(web_data: Path) -> dict[str, Any]:
    path = library_path(web_data)
    if not path.exists():
        return _empty_state()
    data = load_yaml(path) or {}
    if not isinstance(data, dict):
        return _empty_state()
    state = _empty_state()
    state["root"] = str(data.get("root") or "")
    state["focus_id"] = str(data.get("focus_id") or "")
    items_raw = data.get("items")
    if isinstance(items_raw, list):
        for item in items_raw:
            if not isinstance(item, dict):
                continue
            if not item.get("id"):
                continue
            state["items"].append(
                {
                    "id": str(item["id"]),
                    "file": str(item.get("file") or ""),
                }
            )
    links_raw = data.get("links")
    if isinstance(links_raw, list):
        for link in links_raw:
            if not isinstance(link, dict):
                continue
            if not link.get("id") or not link.get("source") or not link.get("target"):
                continue
            state["links"].append(
                {
                    "id": str(link["id"]),
                    "source": str(link["source"]),
                    "target": str(link["target"]),
                    "label": str(link.get("label") or "References"),
                }
            )
    # Drop dangling focus or links pointing at unknown items.
    item_ids = {it["id"] for it in state["items"]}
    if state["focus_id"] not in item_ids:
        state["focus_id"] = ""
    state["links"] = [
        l for l in state["links"] if l["source"] in item_ids and l["target"] in item_ids
    ]
    return state


def save_library(web_data: Path, state: dict[str, Any]) -> None:
    payload = {
        "version": "3",
        "root": state.get("root", ""),
        "focus_id": state.get("focus_id", ""),
        "items": [
            {"id": it["id"], "file": it.get("file", "")}
            for it in state.get("items", [])
        ],
        "links": [
            {
                "id": l["id"],
                "source": l["source"],
                "target": l["target"],
                "label": l.get("label", "References"),
            }
            for l in state.get("links", [])
        ],
    }
    dump_yaml(library_path(web_data), payload)


def _normalize_abs(path: str | Path) -> Path:
    return Path(str(path)).expanduser().resolve()


def set_root(state: dict[str, Any], path: str) -> dict[str, Any]:
    if not path:
        raise ValueError("Library root path is empty")
    abs_path = _normalize_abs(path)
    if not abs_path.exists():
        raise ValueError(f"Library root does not exist: {abs_path}")
    if not abs_path.is_dir():
        raise ValueError(f"Library root is not a directory: {abs_path}")
    if not os.access(abs_path, os.R_OK):
        raise ValueError(f"Library root is not readable: {abs_path}")
    state["root"] = str(abs_path)
    return state


def _ensure_within_root(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Path is outside the library root ({root}): {target}"
        ) from exc


def scan_folder_listing(state: dict[str, Any], sub_path: str | None = None) -> dict[str, Any]:
    root = state.get("root") or ""
    if not root:
        raise ValueError("Library root is not set")
    root_path = _normalize_abs(root)
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"Library root does not exist: {root_path}")
    target = root_path if not sub_path else _normalize_abs(sub_path)
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Folder does not exist: {target}")
    _ensure_within_root(root_path, target)

    dirs: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            dirs.append({"name": entry.name, "path": str(entry)})
            continue
        if not is_ingestible_file(entry):
            continue
        files.append(
            {
                "name": entry.name,
                "path": str(entry),
                "size": entry.stat().st_size,
            }
        )
    parent = None
    if target != root_path:
        parent = str(target.parent)
    return {
        "root": str(root_path),
        "cwd": str(target),
        "parent": parent,
        "dirs": dirs,
        "files": files,
    }


def browse_for_root(path: str | None = None) -> dict[str, Any]:
    """Browse directories on the server to pick a library root (before root is set)."""
    if not path:
        home = Path.home()
        seeds: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in (Path.cwd(), home, home / "Documents", home / "Desktop"):
            try:
                resolved = candidate.expanduser().resolve()
            except OSError:
                continue
            key = str(resolved)
            if key in seen or not resolved.is_dir():
                continue
            if not os.access(resolved, os.R_OK):
                continue
            seen.add(key)
            seeds.append({"name": resolved.name or key, "path": key, "label": key})
        return {"mode": "pick_root", "cwd": "", "parent": None, "dirs": seeds, "files": []}

    target = _normalize_abs(path)
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Folder does not exist: {target}")
    if not os.access(target, os.R_OK):
        raise ValueError(f"Folder is not readable: {target}")

    dirs: list[dict[str, Any]] = []
    file_count = 0
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            if os.access(entry, os.R_OK):
                dirs.append({"name": entry.name, "path": str(entry.resolve())})
            continue
        if is_ingestible_file(entry):
            file_count += 1

    parent = None
    try:
        if target != target.parent:
            parent = str(target.parent)
    except (ValueError, OSError):
        parent = None

    return {
        "mode": "pick_root",
        "cwd": str(target),
        "parent": parent,
        "dirs": dirs,
        "files": [],
        "spec_file_count": file_count,
    }


def validate_inside_root(state: dict[str, Any], file_path: str) -> Path:
    root = state.get("root") or ""
    if not root:
        raise ValueError("Library root is not set")
    root_path = _normalize_abs(root)
    abs_path = _normalize_abs(file_path)
    if not abs_path.exists() or not abs_path.is_file():
        raise ValueError(f"File does not exist: {abs_path}")
    _ensure_within_root(root_path, abs_path)
    return abs_path


# ---------------------------------------------------------------------------
# Items & links
# ---------------------------------------------------------------------------


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _ensure_item(state: dict[str, Any], item_id: str) -> dict[str, Any]:
    for it in state.get("items", []):
        if it["id"] == item_id:
            return it
    raise KeyError(f"Library item not found: {item_id}")


def add_item(state: dict[str, Any], file_path: str | None = None) -> dict[str, Any]:
    item = {"id": _new_id("LIB"), "file": ""}
    if file_path:
        validate_inside_root(state, file_path)
        item["file"] = str(_normalize_abs(file_path))
    state.setdefault("items", []).append(item)
    if not state.get("focus_id"):
        state["focus_id"] = item["id"]
    return item


def update_item(state: dict[str, Any], item_id: str, file_path: str | None) -> dict[str, Any]:
    item = _ensure_item(state, item_id)
    if file_path is None or file_path == "":
        item["file"] = ""
    else:
        validate_inside_root(state, file_path)
        item["file"] = str(_normalize_abs(file_path))
    return item


def delete_item(state: dict[str, Any], item_id: str) -> int:
    items = state.setdefault("items", [])
    before = len(items)
    state["items"] = [it for it in items if it["id"] != item_id]
    if before == len(state["items"]):
        raise KeyError(f"Library item not found: {item_id}")
    removed_links = [l for l in state.get("links", []) if l["source"] == item_id or l["target"] == item_id]
    state["links"] = [l for l in state.get("links", []) if l not in removed_links]
    if state.get("focus_id") == item_id:
        # Pick a new focus if any item remains, else clear.
        state["focus_id"] = state["items"][0]["id"] if state["items"] else ""
    return len(removed_links)


def set_focus(state: dict[str, Any], item_id: str) -> dict[str, Any]:
    item = _ensure_item(state, item_id)
    state["focus_id"] = item["id"]
    return item


def add_link(state: dict[str, Any], source_id: str, target_id: str | None, label: str) -> dict[str, Any]:
    label = (label or "References").strip() or "References"
    _ensure_item(state, source_id)
    if target_id is None:
        new_target = add_item(state)
        target_id = new_target["id"]
    else:
        _ensure_item(state, target_id)
    if source_id == target_id:
        raise ValueError("A spoke cannot point back at the focus itself")
    link = {
        "id": _new_id("LNK"),
        "source": source_id,
        "target": target_id,
        "label": label,
    }
    state.setdefault("links", []).append(link)
    return link


def update_link(state: dict[str, Any], link_id: str, label: str | None = None) -> dict[str, Any]:
    for l in state.get("links", []):
        if l["id"] == link_id:
            if label is not None:
                cleaned = label.strip()
                l["label"] = cleaned or "References"
            return l
    raise KeyError(f"Library link not found: {link_id}")


def delete_link(state: dict[str, Any], link_id: str, *, delete_target_if_orphan: bool = True) -> dict[str, Any]:
    links = state.get("links", [])
    target = next((l for l in links if l["id"] == link_id), None)
    if target is None:
        raise KeyError(f"Library link not found: {link_id}")
    state["links"] = [l for l in links if l["id"] != link_id]
    removed_item = None
    if delete_target_if_orphan:
        tid = target["target"]
        still_used = any(
            l["source"] == tid or l["target"] == tid for l in state["links"]
        )
        if not still_used and tid != state.get("focus_id"):
            # Remove the spoke item too so the canvas does not pile up dangling slots.
            state["items"] = [it for it in state.get("items", []) if it["id"] != tid]
            removed_item = tid
    return {"link": target, "removed_item": removed_item}


# ---------------------------------------------------------------------------
# Upload helper (OS drag-drop → copy into library root)
# ---------------------------------------------------------------------------


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\- ]+")


def safe_local_name(name: str) -> str:
    name = (name or "").strip().replace("/", "_").replace("\\", "_")
    cleaned = _SAFE_NAME.sub("_", name)
    return cleaned or f"dropped_{int(time.time())}.bin"


def unique_dest(root: Path, filename: str) -> Path:
    base = safe_local_name(filename)
    candidate = root / base
    if not candidate.exists():
        return candidate
    stem, ext = os.path.splitext(base)
    counter = 1
    while True:
        candidate = root / f"{stem} ({counter}){ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def import_dropped_file(state: dict[str, Any], src_path: str | Path, original_name: str | None = None) -> Path:
    """Copy a file (already saved by FastAPI) into the library root.

    Returns the destination absolute path.
    """
    root = state.get("root") or ""
    if not root:
        raise ValueError("Library root is not set")
    root_path = _normalize_abs(root)
    if not root_path.is_dir():
        raise ValueError(f"Library root is not a directory: {root_path}")
    src = Path(src_path)
    if not src.exists():
        raise ValueError(f"Source file missing: {src}")
    dest = unique_dest(root_path, original_name or src.name)
    shutil.copyfile(src, dest)
    return dest
