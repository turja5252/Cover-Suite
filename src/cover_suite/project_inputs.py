# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Load Cover fields from the Databook project and save them beside the cover PDF.

Engine writes the same `cover-inputs.json` when it launches Cover Suite.
Keep this filename and kind in sync with Elite Databook Engine cover_handoff.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_FILENAME = "databook-project.json"
INPUTS_FILENAME = "cover-inputs.json"
INPUTS_KIND = "elite-cover-inputs"
INPUTS_VERSION = 1
FIELD_NAMES = (
    "client",
    "description",
    "location",
    "tag",
    "job_number",
    "revision",
    "tab_title",
    "font",
)
FIELD_ENV = {
    "client": "ELITE_COVER_CLIENT",
    "description": "ELITE_COVER_DESCRIPTION",
    "location": "ELITE_COVER_LOCATION",
    "tag": "ELITE_COVER_TAG",
    "revision": "ELITE_COVER_REVISION",
    "tab_title": "ELITE_COVER_TAB",
    "font": "ELITE_COVER_FONT",
    "job_number": "ELITE_COVER_JOB",
}
PATH_KEYS = ("photo",)


def _clean(value: object) -> str:
    return str(value or "").strip()


def overlay_nonempty(*layers: dict[str, object] | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for layer in layers:
        if not layer:
            continue
        for key, value in layer.items():
            text = _clean(value)
            if text:
                merged[str(key)] = text
    return merged


def fields_from_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    source = os.environ if environ is None else environ
    found: dict[str, str] = {}
    for name, env_name in FIELD_ENV.items():
        text = _clean(source.get(env_name, ""))
        if text:
            found[name] = text
    output = _clean(source.get("ELITE_COVER_OUTPUT", ""))
    if output:
        found["output"] = output
    return found


def find_databook_project(start: Path | None, *, max_up: int = 4) -> Path | None:
    if start is None or not str(start).strip():
        return None
    current = Path(start)
    try:
        current = current.resolve()
    except OSError:
        pass
    if current.is_file():
        current = current.parent
    for _ in range(max_up + 1):
        candidate = current / PROJECT_FILENAME
        if candidate.is_file():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def _read_json(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def fields_from_project(path: Path) -> dict[str, str]:
    raw = _read_json(path)
    info = raw.get("databook_info") if isinstance(raw.get("databook_info"), dict) else {}
    found: dict[str, str] = {}
    for name in FIELD_NAMES:
        text = _clean(info.get(name, ""))
        if text:
            found[name] = text
    tab = _clean(raw.get("cover_tab_title", ""))
    if tab:
        found["tab_title"] = tab
    toc = raw.get("toc_options") if isinstance(raw.get("toc_options"), dict) else {}
    font = _clean(toc.get("font", ""))
    if font:
        found["font"] = font
    return found


def inputs_path(output_dir: Path) -> Path:
    return Path(output_dir) / INPUTS_FILENAME


def load_cover_inputs(output_dir: Path | None) -> dict[str, str]:
    if output_dir is None or not str(output_dir).strip():
        return {}
    folder = Path(output_dir)
    payload = _read_json(inputs_path(folder))
    if payload.get("kind") not in (None, "", INPUTS_KIND):
        return {}
    found: dict[str, str] = {}
    for key, value in payload.items():
        if key in ("kind", "version"):
            continue
        text = _clean(value)
        if not text:
            continue
        if key in PATH_KEYS:
            text = resolve_stored_path(text, folder)
        found[str(key)] = text
    return found


def fields_from_project_folder(output_dir: Path | None) -> dict[str, str]:
    project = find_databook_project(output_dir)
    if project is None:
        return {}
    return fields_from_project(project)


def load_cover_fields(output_dir: Path | None) -> dict[str, str]:
    """Project Databook Info, then last Cover save in that job's Cover folder."""
    return overlay_nonempty(fields_from_project_folder(output_dir), load_cover_inputs(output_dir))


def save_cover_inputs(output_dir: Path | None, payload: dict[str, object]) -> Path | None:
    if output_dir is None or not str(output_dir).strip():
        return None
    folder = Path(output_dir)
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    cleaned: dict[str, object] = {
        "kind": INPUTS_KIND,
        "version": INPUTS_VERSION,
    }
    for key, value in payload.items():
        if key in ("kind", "version"):
            continue
        if isinstance(value, (int, float, bool)):
            cleaned[key] = value
            continue
        text = _clean(value)
        if text:
            cleaned[key] = text
    target = inputs_path(folder)
    existing = _read_json(target)
    merged = {**existing, **cleaned}
    merged["kind"] = INPUTS_KIND
    merged["version"] = INPUTS_VERSION
    try:
        target.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return None
    return target


def resolve_stored_path(stored: str, start: Path | None = None) -> str:
    text = stored.strip()
    if not text:
        return ""
    path = Path(text)
    try:
        if path.exists():
            return str(path)
    except OSError:
        pass
    if start is None:
        return text
    current = Path(start)
    try:
        current = current.resolve()
    except OSError:
        pass
    if current.is_file():
        current = current.parent
    name = path.name
    for _ in range(6):
        candidate = current / name
        try:
            if candidate.exists():
                return str(candidate)
        except OSError:
            pass
        if current.parent == current:
            break
        current = current.parent
    return text
