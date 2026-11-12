"""Trusted LaTeX rendering from immutable Practice Sheet variant snapshots."""
from enum import Enum
from pathlib import Path
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.document_generation.exams import safe_question_text
from app.practice_sheet_models import PracticeSheetVariant
from app.services.practice_sheets import get_practice_sheet


class PracticeSheetDocumentType(str, Enum):
    SHEET = "sheet"
    ANSWER_KEY = "answer-key"


_TEMPLATES = {
    PracticeSheetDocumentType.SHEET: "practice_sheet.tex",
    PracticeSheetDocumentType.ANSWER_KEY: "practice_sheet_answer_key.tex",
}


def _plain(value: object | None) -> str:
    return safe_question_text(value) if value is not None else ""


def _questions(variant: PracticeSheetVariant) -> list[dict]:
    snapshot = variant.question_snapshot
    if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
        raise HTTPException(422, "The practice-sheet variant snapshot is invalid")
    questions = snapshot.get("questions")
    required = {"question_id", "position", "points", "response_type", "question_text", "options"}
    if not isinstance(questions, list) or not questions or any(
        not isinstance(item, dict) or not required <= item.keys() for item in questions
    ):
        raise HTTPException(422, "The practice-sheet variant snapshot is incomplete")
    if any(
        not isinstance(item["question_id"], int)
        or not isinstance(item["position"], int)
        or (item["points"] is not None and (not isinstance(item["points"], int) or item["points"] < 1))
        for item in questions
    ) or len({item["question_id"] for item in questions}) != len(questions):
        raise HTTPException(422, "The practice-sheet variant snapshot has invalid questions")
    return sorted(questions, key=lambda item: item["position"])


def _answer(item: dict) -> str:
    if item.get("expected_answer"):
        answer = r"\textbf{Reference answer:} " + safe_question_text(item["expected_answer"])
    elif item.get("correct_boolean") is not None:
        answer = r"\textbf{Correct answer:} " + ("True" if item["correct_boolean"] else "False")
    else:
        options = [
            safe_question_text(option.get("text", ""))
            for option in item["options"]
            if isinstance(option, dict) and option.get("is_correct")
        ]
        if not options:
            raise HTTPException(422, "A variant question has no valid answer for the answer key")
        answer = r"\textbf{Correct option(s):} " + "; ".join(options)
    if item.get("explanation"):
        answer += r"\par\textbf{Guidance:} " + safe_question_text(item["explanation"])
    return answer


def _blocks(questions: list[dict], *, answer_key: bool) -> str:
    lines = [r"\begin{enumerate}"]
    for item in questions:
        points = f" \textbf{{({item['points']} points)}}" if item["points"] is not None else ""
        title = f" ({_plain(item['title'])})" if item.get("title") else ""
        lines.append(r"\item" + points + title + r"\par " + safe_question_text(item["question_text"]))
        if answer_key:
            lines.append(_answer(item))
        elif item["response_type"] == "FREE_RESPONSE":
            lines.append(r"\vspace{25mm}\hrule")
        else:
            lines.append(r"\vspace{8mm}")
    return "\n".join(lines + [r"\end{enumerate}"])


def render_practice_sheet_document(
    session: Session, sheet_id: int, variant_id: int, document_type: PracticeSheetDocumentType
) -> str:
    sheet = get_practice_sheet(session, sheet_id)
    variant = next((item for item in sheet.variants if item.id == variant_id), None)
    if variant is None:
        raise HTTPException(404, "Practice-sheet variant not found")
    questions = _questions(variant)
    total = sum(item["points"] for item in questions if isinstance(item["points"], int))
    values = {
        "SHEET_TITLE": _plain(sheet.title),
        "INSTRUCTIONS": _plain(sheet.instructions),
        "VARIANT_LABEL": _plain(variant.label),
        "TOTAL_POINTS": str(total) if any(item["points"] is not None for item in questions) else "Not specified",
        "QUESTION_BLOCKS": _blocks(questions, answer_key=False),
        "ANSWER_KEY_BLOCKS": _blocks(questions, answer_key=True),
    }
    template = (Path(__file__).parent / "templates" / _TEMPLATES[document_type]).read_text(encoding="utf-8")
    return re.sub(r"@@([A-Z_]+)@@", lambda match: values[match.group(1)], template)
