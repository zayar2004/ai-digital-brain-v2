"""
Image → Knowledge candidates.

Uses OCR when available.
Admin caption/description are ALWAYS preserved as original context.
NEVER invents causes/solutions from visuals alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.ingestion.ocr_reader import read_image
from app.ingestion.quick_teach import extract as quick_extract


@dataclass
class ImageCandidate:
    title: str
    content: str
    source_type: str = "image"
    source_file: str = ""
    machine_name: str | None = None
    unit: str | None = None
    error_code: str | None = None
    confidence: float = 0.4
    raw_ocr: str = ""
    admin_caption: str = ""
    admin_description: str = ""


@dataclass
class ImageIngestion:
    source_type: str = "image"
    original_filename: str = ""
    ocr_available: bool = False
    ocr_error: str | None = None
    ocr_text: str = ""
    candidates: list[ImageCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def ingest_image(
    path: str | Path,
    original_filename: str,
    *,
    admin_caption: str = "",
    admin_description: str = "",
    ocr_lang: str = "eng+mya",
) -> ImageIngestion:
    result = ImageIngestion(original_filename=original_filename)

    ocr = read_image(path, lang=ocr_lang)
    result.ocr_available = ocr.available
    result.ocr_error = ocr.error
    result.ocr_text = ocr.text or ""

    if not ocr.available:
        result.warnings.append(
            "OCR မရနိုင်ပါ။ (pytesseract / tesseract install လိုတယ်)"
        )
    elif not result.ocr_text:
        result.warnings.append("ပုံထဲမှာ စာသား မတွေ့ပါ။")

    # Combine OCR + admin text for downstream extraction
    combined = "\n".join(
        s for s in (result.ocr_text, admin_caption, admin_description) if s
    ).strip()

    # Build one candidate from the combined text (or from caption if OCR empty)
    if combined:
        ext = quick_extract(combined)
        title = (
            admin_caption.strip()[:100]
            or (result.ocr_text.splitlines()[0][:100] if result.ocr_text else "")
            or original_filename
        )

        content_lines: list[str] = []
        if admin_caption:
            content_lines.append(f"[Admin] {admin_caption}")
        if admin_description:
            content_lines.append(f"[Description] {admin_description}")
        if result.ocr_text:
            content_lines.append(f"[OCR]\n{result.ocr_text}")
        content = "\n\n".join(content_lines)

        cand = ImageCandidate(
            title=title or "Image knowledge",
            content=content,
            source_type="image",
            source_file=original_filename,
            machine_name=ext.machine_name,
            unit=ext.unit,
            error_code=ext.error_code,
            confidence=_avg_conf(ext.confidence, default=0.5),
            raw_ocr=result.ocr_text,
            admin_caption=admin_caption,
            admin_description=admin_description,
        )
        result.candidates.append(cand)
    else:
        # Still allow save of caption-only knowledge
        if admin_caption or admin_description:
            ext = quick_extract(admin_caption or admin_description)
            result.candidates.append(ImageCandidate(
                title=(admin_caption or original_filename)[:100],
                content=(admin_caption + "\n\n" + admin_description).strip(),
                source_type="image",
                source_file=original_filename,
                machine_name=ext.machine_name,
                unit=ext.unit,
                error_code=ext.error_code,
                confidence=0.5,
                admin_caption=admin_caption,
                admin_description=admin_description,
            ))
        else:
            result.warnings.append("Caption/Description ထည့်ပါက knowledge အဖြစ် သိမ်းလို့ရပါမယ်။")

    return result


def _avg_conf(conf: dict, default: float = 0.5) -> float:
    if not conf:
        return default
    vals = [v for v in conf.values() if isinstance(v, (int, float))]
    if not vals:
        return default
    return round(sum(vals) / len(vals), 2)
