"""Safe, version-one document settings for printable practice sheets."""
from copy import deepcopy


DEFAULT_DOCUMENT_SETTINGS = {
    "header": {
        "institution_name": "Eötvös Loránd University",
        "course_name": "Discrete Mathematics I",
        "instructor_name": None,
        "document_date": None,
        "logo_visible": True,
    },
    "layout": {
        "paper_size": "A4",
        "margins": "normal",
        "question_spacing": "normal",
    },
    "questions": {
        "show_points": True,
        "answer_space": "medium",
        "numbering_enabled": True,
        "page_break_before_question_ids": [],
    },
}


def default_document_settings() -> dict:
    return deepcopy(DEFAULT_DOCUMENT_SETTINGS)
