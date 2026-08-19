# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
import io
import json
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from cover_suite.cover import (
    COVER_FONT_CASTELLAR,
    COVER_FONT_HELVETICA,
    CoverInfo,
    _register_cover_font,
    _text_first_baseline,
    compose_cover_preview,
    compose_full_cover_preview,
    cover_pdf_name,
    cover_photo_region,
    cover_source_page_count,
    is_cover_pdf,
    normalize_cover_font,
    normalize_photo_page,
    normalize_photo_rotation,
    open_cover_photo,
    photo_window_pdf,
    render_cover_pdf,
    write_cover_pdf,
)
from cover_suite.handoff import write_cover_handoff
from cover_suite.paths import cover_asset


def test_cover_info_lines_skip_empty_and_prefix_tag_rev() -> None:
    info = CoverInfo(
        client="Cenovus",
        description="20'-0\" Dia x 40'-0\" High",
        location="Lloydminster, AB",
        tag="52-T-001",
        job_number="2026-031-1",
        revision="0",
    )
    lines = info.lines()
    assert lines[0] == "Cenovus"
    assert "Tag# 52-T-001" in lines
    assert "Turnover Package" in lines
    assert lines[-1] == "REV 0"
    already = CoverInfo(tag="Tag# 9", revision="rev 1")
    assert already.lines()[3] == "Tag# 9"
    assert already.lines()[-1] == "REV 1"
    empty = CoverInfo().lines()
    assert len(empty) == 6
    assert empty[5] == "Turnover Package"
    assert empty[0] == ""
    assert CoverInfo(revision="").lines()[-1] == "Turnover Package"
    assert CoverInfo(revision="  ").lines()[-1] == "Turnover Package"
    assert _text_first_baseline() == _text_first_baseline()
    custom = CoverInfo(
        client="Ignored",
        use_custom_text=True,
        custom_text="Acme Corp\n\nSpecial Inspection Package\n2026-099\n",
    )
    assert custom.lines() == ["Acme Corp", "", "Special Inspection Package", "2026-099"]
    assert "Turnover Package" not in custom.lines()


def test_cover_pdf_name() -> None:
    assert cover_pdf_name("2026-031-1") == "Cover-2026-031-1.pdf"
    assert cover_pdf_name("") == "Cover.pdf"
    assert cover_pdf_name("2026/031 1") == "Cover-2026-031-1.pdf"


def test_cover_font_choice() -> None:
    assert normalize_cover_font("Helvetica") == COVER_FONT_HELVETICA
    assert normalize_cover_font("") == COVER_FONT_CASTELLAR
    assert normalize_cover_font("castellar") == COVER_FONT_CASTELLAR
    assert _register_cover_font(COVER_FONT_HELVETICA) == "Helvetica-Bold"
    assert _register_cover_font("castellar") != "Helvetica-Bold"


def test_photo_sits_behind_template_circle() -> None:
    window = photo_window_pdf()
    assert window is not None
    x, y, width, height = window
    assert x > 180
    assert y > 300
    assert x + width > 580
    assert y + height > 700
    data = render_cover_pdf(
        CoverInfo(
            client="Cenovus",
            description="20'-0\" Dia x 40'-0\" High",
            location="Lloydminster, AB",
            tag="52-T-001",
            job_number="2026-031-1",
            revision="0",
        )
    )
    reader = PdfReader(io.BytesIO(data), strict=False)
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert abs(float(box.width) - 612) < 1
    assert abs(float(box.height) - 792) < 1
    cover_text = (reader.pages[0].extract_text() or "").replace("\n", " ")
    assert "REV 0" in cover_text
    blank_rev = PdfReader(
        io.BytesIO(render_cover_pdf(CoverInfo(client="Cenovus", job_number="2026-100"))),
        strict=False,
    )
    blank_text = (blank_rev.pages[0].extract_text() or "").replace("\n", " ")
    assert "REV" not in blank_text.upper()
    custom_pdf = render_cover_pdf(
        CoverInfo(
            job_number="2026-031-1",
            use_custom_text=True,
            custom_text="Custom line one\nCustom line two",
        )
    )
    custom_reader = PdfReader(io.BytesIO(custom_pdf), strict=False)
    assert len(custom_reader.pages) == 1


def test_cover_photo_region_zoom_and_pan() -> None:
    image = Image.new("RGB", (400, 200), (255, 0, 0))
    image.paste((0, 0, 255), (200, 0, 400, 200))
    left = cover_photo_region(image, 80, 80, zoom=2.0, pan_x=1.0, pan_y=0.0)
    right = cover_photo_region(image, 80, 80, zoom=2.0, pan_x=-1.0, pan_y=0.0)
    assert left.getpixel((40, 40))[0] > 200
    assert right.getpixel((40, 40))[2] > 200
    tight = cover_photo_region(image, 80, 80, zoom=4.0)
    wide = cover_photo_region(image, 80, 80, zoom=1.0)
    assert tight.tobytes() != wide.tobytes()
    rotated = cover_photo_region(image, 80, 80, rotation=90)
    assert rotated.size == (80, 80)
    assert normalize_photo_rotation(90) == 90
    assert normalize_photo_rotation(450) == 90
    assert normalize_photo_rotation(-90) == 270


def test_compose_cover_preview_matches_cutout_size() -> None:
    photo = cover_asset("elite_cover_photo.jpg")
    preview = compose_cover_preview(photo, zoom=1.5, pan_x=0.2, pan_y=-0.1, width=220, height=260)
    assert preview is not None
    assert preview.size == (220, 260)
    shifted = compose_cover_preview(photo, zoom=1.5, pan_x=-0.8, pan_y=0.4, width=220, height=260)
    assert shifted is not None
    assert preview.tobytes() != shifted.tobytes()


def test_compose_full_cover_preview_is_letter_page() -> None:
    photo = cover_asset("elite_cover_photo.jpg")
    info = CoverInfo(
        client="Cenovus",
        description="20'-0\" Dia x 40'-0\" High",
        location="Lloydminster, AB",
        tag="52-T-001",
        job_number="2026-031-1",
        revision="0",
        photo_path=str(photo),
    )
    preview = compose_full_cover_preview(info, width=200, height=280)
    assert preview is not None
    assert preview.size == (200, 280)
    other = compose_full_cover_preview(
        CoverInfo(client="Different Client", job_number="2026-099-1", photo_path=str(photo)),
        width=200,
        height=280,
    )
    assert other is not None
    assert preview.tobytes() != other.tobytes()


def _write_color_pdf(path: Path, colors: list[tuple[int, int, int]]) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen.canvas import Canvas

    canvas = Canvas(str(path), pagesize=letter)
    for red, green, blue in colors:
        canvas.setFillColorRGB(red / 255, green / 255, blue / 255)
        canvas.rect(0, 0, 400, 400, fill=1, stroke=0)
        canvas.showPage()
    canvas.save()


def test_cover_photo_accepts_pdf_pages(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    _write_color_pdf(pdf, [(220, 20, 20), (20, 20, 220)])
    assert is_cover_pdf(pdf)
    assert cover_source_page_count(pdf) == 2
    assert normalize_photo_page(9, 2) == 2
    first = open_cover_photo(pdf, 1)
    second = open_cover_photo(pdf, 2)
    assert first is not None and second is not None
    assert first.size[0] > 10 and first.size[1] > 10
    assert first.getpixel((40, 40))[0] > 150
    assert second.getpixel((40, 40))[2] > 150
    preview = compose_cover_preview(pdf, page=1, width=180, height=180)
    assert preview is not None
    assert preview.size == (180, 180)
    jpg = cover_asset("elite_cover_photo.jpg")
    assert open_cover_photo(jpg) is not None
    assert cover_source_page_count(jpg) == 1


def test_write_cover_handoff_relative_path(tmp_path: Path) -> None:
    pdf = write_cover_pdf(CoverInfo(client="Cenovus", job_number="2026-031-1"), tmp_path / "Cover-2026-031-1.pdf")
    target = write_cover_handoff(tmp_path, cover_pdf=pdf, tab_title="Cover - 2026-031-1-DB")
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["kind"] == "elite-cover-handoff"
    assert payload["cover_pdf"] == "Cover-2026-031-1.pdf"
    assert payload["tab_title"] == "Cover - 2026-031-1-DB"
    assert pdf.is_file()
    assert pdf.stat().st_size > 10_000
