# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import json
from pathlib import Path

from cover_suite.project_inputs import (
    fields_from_env,
    load_cover_fields,
    overlay_nonempty,
    save_cover_inputs,
)


def test_cover_loads_databook_info_from_project(tmp_path: Path) -> None:
    output = tmp_path / "Output"
    cover = output / "Cover"
    cover.mkdir(parents=True)
    (output / "databook-project.json").write_text(
        json.dumps(
            {
                "databook_info": {
                    "client": "Cenovus",
                    "description": "T-0810 Mods",
                    "location": "Lloydminster, AB",
                    "tag": "T-0810",
                    "job_number": "2026-073-1",
                    "revision": "0",
                },
                "cover_tab_title": "Cover - 2026-073-1-DB",
                "toc_options": {"font": "Helvetica"},
            }
        ),
        encoding="utf-8",
    )
    loaded = load_cover_fields(cover)
    assert loaded["client"] == "Cenovus"
    assert loaded["job_number"] == "2026-073-1"
    assert loaded["tag"] == "T-0810"
    assert loaded["tab_title"] == "Cover - 2026-073-1-DB"
    assert loaded["font"] == "Helvetica"


def test_cover_inputs_round_trip_and_override_project(tmp_path: Path) -> None:
    output = tmp_path / "Output"
    cover = output / "Cover"
    cover.mkdir(parents=True)
    (output / "databook-project.json").write_text(
        json.dumps({"databook_info": {"client": "Old Client", "job_number": "2026-001-1"}}),
        encoding="utf-8",
    )
    photo = cover / "tank.jpg"
    photo.write_bytes(b"fake")
    save_cover_inputs(
        cover,
        {
            "client": "Cenovus",
            "job_number": "2026-073-1",
            "photo": str(photo),
            "photo_zoom": 1.5,
        },
    )
    loaded = load_cover_fields(cover)
    assert loaded["client"] == "Cenovus"
    assert loaded["job_number"] == "2026-073-1"
    assert Path(loaded["photo"]) == photo
    assert loaded["photo_zoom"] == "1.5"


def test_cover_env_overrides_saved_fields() -> None:
    merged = overlay_nonempty(
        {"client": "Saved", "job_number": "2026-001-1"},
        fields_from_env(
            {
                "ELITE_COVER_CLIENT": "Cenovus",
                "ELITE_COVER_JOB": "2026-073-1",
            }
        ),
    )
    assert merged["client"] == "Cenovus"
    assert merged["job_number"] == "2026-073-1"


def test_cover_resolves_photo_by_name_from_project_folder(tmp_path: Path) -> None:
    output = tmp_path / "Output"
    cover = output / "Cover"
    cover.mkdir(parents=True)
    photo = output / "site.jpg"
    photo.write_bytes(b"fake")
    save_cover_inputs(cover, {"photo": r"C:\Users\SarahChan\gone\site.jpg", "client": "Cenovus"})
    loaded = load_cover_fields(cover)
    assert Path(loaded["photo"]) == photo
