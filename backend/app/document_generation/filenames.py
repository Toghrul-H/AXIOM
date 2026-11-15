"""Safe, stable attachment names for staff-only generated PDFs."""
from datetime import date, datetime
import re
from typing import Mapping
import unicodedata


_MAX_FILENAME_LENGTH = 180
_NON_ASCII_FILENAME_CHARACTERS = re.compile(r"[^A-Za-z0-9]+")


def _segment(value: object, fallback: str) -> str:
    """Return an ASCII-only filename segment with no header/path characters."""
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    safe = _NON_ASCII_FILENAME_CHARACTERS.sub("_", normalized).strip("_.")
    return safe or fallback


def _date_text(settings: object) -> str:
    header = settings.get("header", {}) if isinstance(settings, Mapping) else {}
    value = header.get("document_date") if isinstance(header, Mapping) else None
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, str):
        try:
            return date.fromisoformat(value).strftime("%d.%m.%Y")
        except ValueError:
            pass
    return "Undated"


def _filename(title: object, settings: object, *parts: object, extension: str = ".pdf") -> str:
    if extension not in {".pdf", ".tex"}:
        raise ValueError("Unsupported document filename extension")
    suffix = "_".join((_date_text(settings), *(_segment(part, "Document") for part in parts)))
    title_limit = _MAX_FILENAME_LENGTH - len(suffix) - len("_") - len(extension)
    safe_title = _segment(title, "AXIOM_Document")[:max(1, title_limit)]
    return f"{safe_title}_{suffix}{extension}"


def _exam_settings(exam: object) -> object:
    settings = getattr(exam, "document_settings", {})
    snapshot = getattr(exam, "question_snapshot", None)
    if getattr(exam, "status", None) == "finalized" and isinstance(snapshot, Mapping):
        # Matches rendering: newer finalized exams freeze their saved layout.
        settings = snapshot.get("document_settings", settings)
    return settings


def _exam_filename(exam: object, document_type: object, extension: str) -> str:
    kind = getattr(document_type, "value", str(document_type))
    if kind not in {"exam", "answer-key"}:
        raise ValueError("Unsupported exam document type")
    parts: list[object] = ["Exam", getattr(exam, "id")]
    if kind == "answer-key":
        parts.extend(("Answer", "Key"))
    return _filename(getattr(exam, "title"), _exam_settings(exam), *parts, extension=extension)


def exam_pdf_filename(exam: object, document_type: object) -> str:
    return _exam_filename(exam, document_type, ".pdf")


def exam_tex_filename(exam: object, document_type: object) -> str:
    return _exam_filename(exam, document_type, ".tex")


def _practice_sheet_filename(sheet: object, variant: object, document_type: object, extension: str) -> str:
    kind = getattr(document_type, "value", str(document_type))
    if kind not in {"sheet", "answer-key"}:
        raise ValueError("Unsupported practice-sheet document type")
    parts: list[object] = [getattr(variant, "label"), "Practice", "Sheet", getattr(sheet, "id"), getattr(variant, "id")]
    if kind == "answer-key":
        parts.extend(("Answer", "Key"))
    return _filename(getattr(sheet, "title"), getattr(sheet, "document_settings", {}), *parts, extension=extension)


def practice_sheet_pdf_filename(sheet: object, variant: object, document_type: object) -> str:
    return _practice_sheet_filename(sheet, variant, document_type, ".pdf")


def practice_sheet_tex_filename(sheet: object, variant: object, document_type: object) -> str:
    return _practice_sheet_filename(sheet, variant, document_type, ".tex")
