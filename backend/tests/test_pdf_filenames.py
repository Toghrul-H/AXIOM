from types import SimpleNamespace

from app.document_generation.filenames import exam_pdf_filename, practice_sheet_pdf_filename


def settings(value=None):
    return {"header": {"document_date": value}}


def test_exam_filenames_use_saved_or_frozen_dates_and_distinct_ids():
    exam = SimpleNamespace(id=42, title="Mídtérm / 2026\r\n", status="draft", document_settings=settings("2026-11-15"), question_snapshot=None)
    assert exam_pdf_filename(exam, "exam") == "Midterm_2026_15.11.2026_Exam_42.pdf"
    assert exam_pdf_filename(exam, "answer-key") == "Midterm_2026_15.11.2026_Exam_42_Answer_Key.pdf"
    other = SimpleNamespace(**{**exam.__dict__, "id": 43})
    assert exam_pdf_filename(other, "exam") != exam_pdf_filename(exam, "exam")

    finalized = SimpleNamespace(
        id=42,
        title="Midterm",
        status="finalized",
        document_settings=settings("2026-01-01"),
        question_snapshot={"document_settings": settings("2026-11-15")},
    )
    assert "15.11.2026" in exam_pdf_filename(finalized, "exam")


def test_practice_filenames_include_immutable_variant_identity_and_handle_missing_dates():
    sheet = SimpleNamespace(id=9, title="Practice Sheet", document_settings=settings(None))
    variant_a = SimpleNamespace(id=17, label="A")
    variant_b = SimpleNamespace(id=18, label="B")
    assert practice_sheet_pdf_filename(sheet, variant_a, "sheet") == "Practice_Sheet_Undated_A_Practice_Sheet_9_17.pdf"
    assert practice_sheet_pdf_filename(sheet, variant_a, "answer-key") == "Practice_Sheet_Undated_A_Practice_Sheet_9_17_Answer_Key.pdf"
    assert practice_sheet_pdf_filename(sheet, variant_a, "sheet") != practice_sheet_pdf_filename(sheet, variant_b, "sheet")


def test_filename_sanitization_and_length_limit_are_safe():
    exam = SimpleNamespace(
        id=7,
        title="../../\x00A <very> long: title? " + "é" * 240,
        status="draft",
        document_settings=settings("not-a-date"),
        question_snapshot=None,
    )
    filename = exam_pdf_filename(exam, "exam")
    assert filename.endswith("_Undated_Exam_7.pdf")
    assert len(filename) <= 180
    assert all(character.isascii() and (character.isalnum() or character in "_.-") for character in filename)
