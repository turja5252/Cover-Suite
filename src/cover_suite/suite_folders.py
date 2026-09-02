# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Last Output / Add-PDFs folders shared by Engine, Cover Suite, and WELD Suite."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_FOLDER = "EliteIntegrity"
FILENAME = "suite-folders.json"


def suite_folders_path() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / APP_FOLDER / FILENAME


def load_suite_folders() -> dict[str, str]:
    path = suite_folders_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("output", "open"):
        value = str(raw.get(key) or "").strip()
        if value:
            out[key] = value
    return out


def remember_suite_folders(
    *,
    output: str | Path | None = None,
    open_dir: str | Path | None = None,
) -> None:
    data = load_suite_folders()
    if output is not None and str(output).strip():
        folder = Path(output)
        try:
            data["output"] = str(folder.expanduser().resolve())
        except OSError:
            data["output"] = str(folder)
    if open_dir is not None and str(open_dir).strip():
        path = Path(open_dir)
        folder = path.parent if path.is_file() or path.suffix else path
        if not folder.is_dir() and path.parent.is_dir():
            folder = path.parent
        try:
            data["open"] = str(folder.expanduser().resolve())
        except OSError:
            data["open"] = str(folder)
    if not data:
        return
    path = suite_folders_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def last_suite_folder(*keys: str) -> Path | None:
    data = load_suite_folders()
    wanted = keys or ("open", "output")
    for key in wanted:
        token = data.get(key, "").strip()
        if not token:
            continue
        path = Path(token)
        if path.is_dir():
            return path
        if path.is_file():
            return path.parent
    return None


def last_add_pdfs_dir(*fallbacks: str | Path | None) -> str | None:
    """Folder a picker should open in: last browse across the suite, then fallbacks."""
    return picker_start_dir(*fallbacks)


def picker_start_dir(*fallbacks: str | Path | None) -> str | None:
    """Folder a file dialog should open in.

    Shared last browse (any of Engine / Cover / WELD) wins, then the caller’s
    fallbacks, then the shared Output folder.
    """
    found = last_suite_folder("open")
    if found is not None:
        return str(found)
    for item in fallbacks:
        if item is None or not str(item).strip():
            continue
        path = Path(item)
        if path.is_file():
            path = path.parent
        if path.is_dir():
            return str(path)
    found = last_suite_folder("output")
    return str(found) if found else None


def last_engine_suite_output(suite_name: str) -> Path | None:
    """Engine's last job Output Folder, pointed at Cover/ or WELD/ when that is the suite."""
    root = last_suite_folder("output")
    if root is None:
        return None
    if root.name.casefold() == suite_name.casefold():
        return root
    return root / suite_name
