"""Safe, version-one print settings for Exam Builder documents."""
from copy import deepcopy


DEFAULT_EXAM_DOCUMENT_SETTINGS = {
    "header": {
        "institution_name": "Eötvös Loránd University",
        "course_name": "Discrete Mathematics I",
        "instructor_name": None,
        "document_date": None,
        "duration_minutes": None,
    },
    "layout": {
        "paper_size": "A4",
        "margins": "normal",
        "question_spacing": "normal",
        "page_numbering": True,
    },
    "student_fields": {
        "show_name": True,
        "show_neptun_code": True,
        "show_date": True,
    },
    "questions": {
        "show_points": True,
        "answer_space": "medium",
        "numbering_enabled": True,
        "page_break_before_question_ids": [],
    },
}


def default_exam_document_settings() -> dict:
    return deepcopy(DEFAULT_EXAM_DOCUMENT_SETTINGS)
