# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path


def app_anchor() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundled_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return app_anchor()


def cover_asset(name: str) -> Path:
    packaged = Path(str(resources.files("cover_suite").joinpath("data", name)))
    if packaged.is_file():
        return packaged
    fallback = bundled_root() / "src" / "cover_suite" / "data" / name
    if fallback.is_file():
        return fallback
    return packaged


def default_settings_path() -> Path:
    local = Path.home() / "AppData" / "Local" / "EliteCoverSuite"
    local.mkdir(parents=True, exist_ok=True)
    return local / "settings.json"
