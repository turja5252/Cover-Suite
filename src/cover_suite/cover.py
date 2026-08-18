# Created by Tanzim Nasir
# Copyright (c) 2026 Tanzim Nasir.
# Built for Elite Integrity Services.
# Unauthorized use by other companies is prohibited.
"""Draw the Elite databook cover: branded frame, circle photo, footer, text box."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from cover_suite.paths import cover_asset

PAGE_WIDTH, PAGE_HEIGHT = letter
TEXT_SIZE = 20.0
# Word text-box paragraphs: 20pt with default line=259/240 and 8pt after.
LEADING = TEXT_SIZE * 259.0 / 240.0 + 8.0
COVER_FONT = "CoverSerif"
COVER_FONT_CASTELLAR = "castellar"
COVER_FONT_HELVETICA = "helvetica"
# Word crops 31.878% off the bottom of EliteCover_PS.png (srcRect b="31878").
FRAME_CROP_BOTTOM = 31878 / 100000
# Frame placement on the letter page, matching Word (PDF origin is bottom-left).
FRAME_PDF = (-6.37, 239.51, 618.70, 569.25)
# Cover text sits in the lower-left white band, beside the branding. Top-aligned so
# extra/missing lines do not move the block.
TEXT_BOX = (14.25, 40.0, 356.25, 200.0)
TEXT_INSET_LEFT = 7.2
TEXT_INSET_TOP = 3.6
# Same footer placement as before the Word-offset experiment.
BRANDING_PDF = (420.0, 26.0, 158.0, 200.0)
# PDF box for the template's transparent circle (x, y, width, height).
_PHOTO_WINDOW: tuple[float, float, float, float] | None = None
_CROPPED_FRAME: Image.Image | None = None


@dataclass(frozen=True)
class CoverInfo:
    client: str = ""
    description: str = ""
    location: str = ""
    tag: str = ""
    job_number: str = ""
    revision: str = ""
    photo_path: str = ""
    photo_zoom: float = 1.0
    photo_pan_x: float = 0.0
    photo_pan_y: float = 0.0
    photo_rotation: int = 0
    photo_page: int = 1
    use_custom_text: bool = False
    custom_text: str = ""
    font: str = COVER_FONT_CASTELLAR

    def lines(self) -> list[str]:
        if self.use_custom_text:
            raw = self.custom_text.replace("\r\n", "\n").replace("\r", "\n")
            parts = raw.split("\n")
            while parts and not parts[-1].strip():
                parts.pop()
            return parts
        tag = self.tag.strip()
        if tag and not tag.casefold().startswith("tag"):
            tag = f"Tag# {tag}"
        rows = [
            self.client.strip(),
            self.description.strip(),
            self.location.strip(),
            tag,
            self.job_number.strip(),
            "Turnover Package",
        ]
        revision = revision_line(self.revision)
        if revision:
            rows.append(revision)
        return rows


def revision_line(value: str) -> str:
    """Return 'REV 0' when a revision is set; empty string if the field is blank."""
    revision = value.strip()
    if not revision:
        return ""
    if revision.casefold().startswith("rev"):
        rest = revision[3:].strip(" .:").strip()
        return f"REV {rest}" if rest else "REV"
    return f"REV {revision}"


def normalize_cover_font(value: object) -> str:
    text = str(value or "").strip().casefold()
    if text == COVER_FONT_HELVETICA:
        return COVER_FONT_HELVETICA
    return COVER_FONT_CASTELLAR


def _register_cover_font(choice: object = COVER_FONT_CASTELLAR) -> str:
    if normalize_cover_font(choice) == COVER_FONT_HELVETICA:
        return "Helvetica-Bold"
    if COVER_FONT in pdfmetrics.getRegisteredFontNames():
        return COVER_FONT
    fonts = Path(r"C:\Windows\Fonts")
    for candidate in (
        fonts / "CASTELAR.TTF",
        fonts / "Castellar.ttf",
    ):
        if candidate.is_file():
            pdfmetrics.registerFont(TTFont(COVER_FONT, str(candidate)))
            return COVER_FONT
    return "Times-Bold"


def cover_pdf_name(job_number: str = "") -> str:
    job = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in job_number.strip())
    job = job.strip("-")
    return f"Cover-{job}.pdf" if job else "Cover.pdf"


def _cropped_frame_image() -> Image.Image | None:
    global _CROPPED_FRAME
    if _CROPPED_FRAME is not None:
        return _CROPPED_FRAME
    path = cover_asset("elite_cover_frame.png")
    if not path.is_file():
        return None
    with Image.open(path) as frame:
        image = frame.convert("RGBA")
    width, height = image.size
    visible_h = max(1, int(round(height * (1.0 - FRAME_CROP_BOTTOM))))
    _CROPPED_FRAME = image.crop((0, 0, width, visible_h))
    return _CROPPED_FRAME


def _frame_hole_bbox_px(frame: Image.Image) -> tuple[int, int, int, int] | None:
    """Bounding box of the template's transparent circle, in cropped-frame pixels."""
    hole_mask = frame.getchannel("A").point(lambda alpha: 255 if alpha == 0 else 0)
    bbox = hole_mask.getbbox()
    if bbox is None:
        return None
    pad = 2
    min_x = max(0, bbox[0] - pad)
    min_y = max(0, bbox[1] - pad)
    max_x = min(frame.width - 1, bbox[2] - 1 + pad)
    max_y = min(frame.height - 1, bbox[3] - 1 + pad)
    return (min_x, min_y, max_x, max_y)


def photo_window_pdf(frame_path: Path | None = None) -> tuple[float, float, float, float] | None:
    """Where the job photo sits, in PDF points. The template artwork cuts the circle."""
    global _PHOTO_WINDOW
    if _PHOTO_WINDOW is not None and frame_path is None:
        return _PHOTO_WINDOW
    if frame_path is not None:
        with Image.open(frame_path) as frame:
            cropped = frame.convert("RGBA")
    else:
        cropped = _cropped_frame_image()
    if cropped is None:
        return None
    bbox = _frame_hole_bbox_px(cropped)
    width, height = cropped.size
    if bbox is None or width < 1 or height < 1:
        return None
    left_px, top_px, right_px, bottom_px = bbox
    fx, fy, fw, fh = FRAME_PDF
    x = fx + left_px / width * fw
    box_w = (right_px - left_px + 1) / width * fw
    box_h = (bottom_px - top_px + 1) / height * fh
    y = fy + (height - (bottom_px + 1)) / height * fh
    window = (x, y, box_w, box_h)
    if frame_path is None:
        _PHOTO_WINDOW = window
    return window


def normalize_photo_rotation(value: object) -> int:
    """Clockwise degrees in {0, 90, 180, 270}."""
    try:
        degrees = int(round(float(value or 0))) % 360
    except (TypeError, ValueError):
        return 0
    if degrees in {90, 180, 270}:
        return degrees
    return 0


def _apply_photo_rotation(image: Image.Image, rotation: int) -> Image.Image:
    degrees = normalize_photo_rotation(rotation)
    if degrees == 90:
        return image.transpose(Image.Transpose.ROTATE_270)
    if degrees == 180:
        return image.transpose(Image.Transpose.ROTATE_180)
    if degrees == 270:
        return image.transpose(Image.Transpose.ROTATE_90)
    return image


def is_cover_pdf(path: Path) -> bool:
    return path.suffix.casefold() == ".pdf"


def cover_source_page_count(path: Path) -> int:
    """Page count for a cover PDF; 1 for photos or unreadable files."""
    if not path.is_file() or not is_cover_pdf(path):
        return 1
    try:
        import pymupdf
    except ImportError:
        return 1
    try:
        doc = pymupdf.open(path)
    except Exception:
        return 1
    try:
        return max(1, int(doc.page_count or 1))
    finally:
        doc.close()


def normalize_photo_page(value: object, page_count: int = 1) -> int:
    total = max(1, int(page_count or 1))
    try:
        page = int(value or 1)
    except (TypeError, ValueError):
        page = 1
    return min(total, max(1, page))


def open_cover_photo(path: Path, page: int = 1) -> Image.Image | None:
    """Load a cover photo. PDFs render the chosen page so pan/zoom/rotate still work."""
    if not path.is_file():
        return None
    if is_cover_pdf(path):
        return _pdf_page_image(path, page)
    try:
        return Image.open(path).convert("RGB")
    except OSError:
        return None


def _pdf_page_image(path: Path, page: int) -> Image.Image | None:
    try:
        import pymupdf
    except ImportError:
        return None
    try:
        doc = pymupdf.open(path)
    except Exception:
        return None
    try:
        if doc.page_count < 1:
            return None
        index = normalize_photo_page(page, doc.page_count) - 1
        pix = doc[index].get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    except Exception:
        return None
    finally:
        doc.close()


def cover_photo_region(
    image: Image.Image,
    box_w: float,
    box_h: float,
    *,
    zoom: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
    rotation: int = 0,
) -> Image.Image:
    """Crop the job photo to the cover window. zoom 1 fills the cutout; pan is -1..1."""
    rgb = _apply_photo_rotation(image.convert("RGB"), rotation)
    width, height = rgb.size
    target_w = max(1, int(round(box_w)))
    target_h = max(1, int(round(box_h)))
    if width < 1 or height < 1:
        return Image.new("RGB", (target_w, target_h), (0, 0, 0))
    zoom = max(1.0, min(8.0, float(zoom)))
    pan_x = max(-1.0, min(1.0, float(pan_x)))
    pan_y = max(-1.0, min(1.0, float(pan_y)))
    target_aspect = target_w / target_h
    if width / height > target_aspect:
        crop_h = height / zoom
        crop_w = crop_h * target_aspect
    else:
        crop_w = width / zoom
        crop_h = crop_w / target_aspect
    crop_w = min(width, max(1.0, crop_w))
    crop_h = min(height, max(1.0, crop_h))
    extra_x = max(0.0, width - crop_w)
    extra_y = max(0.0, height - crop_h)
    left = extra_x / 2.0 - pan_x * extra_x / 2.0
    top = extra_y / 2.0 - pan_y * extra_y / 2.0
    left = max(0.0, min(extra_x, left))
    top = max(0.0, min(extra_y, top))
    cropped = rgb.crop((int(left), int(top), int(left + crop_w), int(top + crop_h)))
    if cropped.size != (target_w, target_h):
        cropped = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
    return cropped


def _cover_cropped_photo(
    photo: Path,
    box_w: float,
    box_h: float,
    *,
    zoom: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
    rotation: int = 0,
    page: int = 1,
) -> ImageReader | None:
    image = open_cover_photo(photo, page)
    if image is None:
        return None
    if image.width < 1 or image.height < 1 or box_w < 1 or box_h < 1:
        return None
    pixel_w = max(int(round(box_w * 2)), 800)
    pixel_h = max(1, int(round(pixel_w * box_h / box_w)))
    cropped = cover_photo_region(
        image, pixel_w, pixel_h, zoom=zoom, pan_x=pan_x, pan_y=pan_y, rotation=rotation
    )
    buffer = io.BytesIO()
    cropped.save(buffer, format="JPEG", quality=92)
    buffer.seek(0)
    return ImageReader(buffer)


def compose_cover_preview(
    photo: Path,
    *,
    zoom: float = 1.0,
    pan_x: float = 0.0,
    pan_y: float = 0.0,
    rotation: int = 0,
    page: int = 1,
    width: int = 320,
    height: int = 320,
) -> Image.Image | None:
    """Preview the real cover cutout (partial circle + arcs), not a fake full circle."""
    frame = _cropped_frame_image()
    if frame is None:
        return None
    hole = _frame_hole_bbox_px(frame)
    ring = max(24, int(round(min(frame.width, frame.height) * 0.06)))
    if hole is None:
        crop = (0, 0, frame.width, frame.height)
    else:
        crop = (
            max(0, hole[0] - ring),
            max(0, hole[1] - ring),
            min(frame.width, hole[2] + 1 + ring),
            min(frame.height, hole[3] + 1 + ring),
        )
    crop_w = max(1, crop[2] - crop[0])
    crop_h = max(1, crop[3] - crop[1])
    scale = min(width / crop_w, height / crop_h)
    out_w = max(1, int(crop_w * scale))
    out_h = max(1, int(crop_h * scale))
    frame_crop = frame.crop(crop).resize((out_w, out_h), Image.Resampling.LANCZOS)
    base = Image.new("RGBA", (out_w, out_h), (255, 255, 255, 255))
    if hole is not None and photo.is_file():
        source = open_cover_photo(photo, page)
        if source is not None:
            hx0 = int((hole[0] - crop[0]) * scale)
            hy0 = int((hole[1] - crop[1]) * scale)
            hx1 = int((hole[2] + 1 - crop[0]) * scale)
            hy1 = int((hole[3] + 1 - crop[1]) * scale)
            box_w = max(1, hx1 - hx0)
            box_h = max(1, hy1 - hy0)
            placed = cover_photo_region(
                source, box_w, box_h, zoom=zoom, pan_x=pan_x, pan_y=pan_y, rotation=rotation
            )
            base.paste(placed, (hx0, hy0))
    preview = Image.alpha_composite(base, frame_crop)
    out = Image.new("RGBA", (width, height), (5, 4, 3, 255))
    out.paste(preview, ((width - out_w) // 2, (height - out_h) // 2))
    return out


def _cover_lines_fitted(lines: list[str], font: str, size: float, max_width: float) -> list[str]:
    fitted: list[str] = []
    for line in lines:
        if stringWidth(line, font, size) <= max_width:
            fitted.append(line)
            continue
        words = line.split()
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if not current or stringWidth(trial, font, size) <= max_width:
                current = trial
            else:
                fitted.append(current)
                current = word
        if current:
            fitted.append(current)
    return fitted


def _text_first_baseline() -> float:
    _x, y, _w, height = TEXT_BOX
    box_top = y + height
    return box_top - TEXT_INSET_TOP - TEXT_SIZE * 0.8


def _draw_cover_text(canvas: Canvas, font: str, lines: list[str], *, wrap: bool = False) -> None:
    box_x, box_y, box_w, _box_h = TEXT_BOX
    center_x = box_x + box_w / 2
    max_width = box_w - TEXT_INSET_LEFT * 2
    canvas.setFillColorRGB(0.08, 0.08, 0.08)
    canvas.setFont(font, TEXT_SIZE)
    y = _text_first_baseline()
    min_y = box_y - TEXT_SIZE * 0.5
    for line in lines:
        if wrap:
            chunks = _cover_lines_fitted([line.strip()], font, TEXT_SIZE, max_width) if line.strip() else [""]
        else:
            text = line.strip()
            if text:
                fitted = _cover_lines_fitted([text], font, TEXT_SIZE, max_width)
                chunks = [fitted[0] if fitted else text]
            else:
                chunks = [""]
        for chunk in chunks:
            if y < min_y:
                return
            if chunk:
                canvas.drawCentredString(center_x, y, chunk)
            y -= LEADING


def _frame_reader() -> ImageReader | None:
    cropped = _cropped_frame_image()
    if cropped is None:
        return None
    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def render_cover_pdf(info: CoverInfo) -> bytes:
    font = _register_cover_font(info.font)
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=letter)
    branding = cover_asset("elite_cover_branding.png")
    photo_text = (info.photo_path or "").strip()
    photo = Path(photo_text) if photo_text else cover_asset("elite_cover_photo.jpg")
    if not photo.is_file():
        photo = cover_asset("elite_cover_photo.jpg")

    window = photo_window_pdf()
    if photo.is_file() and window is not None:
        x, y, box_w, box_h = window
        reader = _cover_cropped_photo(
            photo,
            box_w,
            box_h,
            zoom=info.photo_zoom,
            pan_x=info.photo_pan_x,
            pan_y=info.photo_pan_y,
            rotation=info.photo_rotation,
            page=info.photo_page,
        )
        if reader is not None:
            canvas.drawImage(reader, x, y, width=box_w, height=box_h)

    frame_reader = _frame_reader()
    if frame_reader is not None:
        fx, fy, fw, fh = FRAME_PDF
        canvas.drawImage(frame_reader, fx, fy, width=fw, height=fh, mask="auto")

    if branding.is_file():
        bx, by, bw, bh = BRANDING_PDF
        canvas.drawImage(
            str(branding),
            bx,
            by,
            width=bw,
            height=bh,
            mask="auto",
            preserveAspectRatio=True,
        )

    _draw_cover_text(canvas, font, info.lines(), wrap=info.use_custom_text)

    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def write_cover_pdf(info: CoverInfo, dest: Path) -> Path:
    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(render_cover_pdf(info))
    return dest


def cover_pdf_reader(info: CoverInfo) -> PdfReader:
    return PdfReader(io.BytesIO(render_cover_pdf(info)), strict=False)
