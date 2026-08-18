# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Write cover-handoff.json so Databook can import the generated cover PDF."""

from __future__ import annotations

import json
from pathlib import Path

HANDOFF_FILENAME = "cover-handoff.json"
HANDOFF_KIND = "elite-cover-handoff"
HANDOFF_VERSION = 1


def write_cover_handoff(
    output_dir: Path,
    *,
    cover_pdf: Path,
    tab_title: str = "",
) -> Path:
    output_dir = output_dir.resolve()
    cover_pdf = cover_pdf.resolve()
    try:
        relative = cover_pdf.relative_to(output_dir).as_posix()
    except ValueError:
        relative = str(cover_pdf)
    payload = {
        "kind": HANDOFF_KIND,
        "version": HANDOFF_VERSION,
        "cover_pdf": relative,
        "tab_title": (tab_title or "").strip(),
    }
    target = output_dir / HANDOFF_FILENAME
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target
