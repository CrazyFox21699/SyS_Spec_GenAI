"""Local-folder library backing the Library Map tab."""

from src.library.library_state import (
    LIBRARY_FILE,
    add_item,
    add_link,
    delete_item,
    delete_link,
    import_dropped_file,
    library_path,
    load_library,
    save_library,
    scan_folder_listing,
    browse_for_root,
    set_focus,
    set_root,
    update_item,
    update_link,
    validate_inside_root,
)

__all__ = [
    "LIBRARY_FILE",
    "add_item",
    "add_link",
    "delete_item",
    "delete_link",
    "import_dropped_file",
    "library_path",
    "load_library",
    "save_library",
    "scan_folder_listing",
    "browse_for_root",
    "set_focus",
    "set_root",
    "update_item",
    "update_link",
    "validate_inside_root",
]
