"""Trusted LaTeX rendering for staff-authored Exam Builder documents."""
from enum import Enum
from pathlib import Path
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.assessment_models import AssessmentConfiguration
from app.document_generation.latex import TO_BE_ANNOUNCED, escape
from app.exam_models import Exam
from app.models import Question
from app.services.exams import get_exam


class ExamDocumentType(str, Enum):
    EXAM = "exam"
    ANSWER_KEY = "answer-key"


_TEMPLATES = {
    ExamDocumentType.EXAM: "exam.tex",
    ExamDocumentType.ANSWER_KEY: "exam_answer_key.tex",
}
_SAFE_MATH_COMMANDS = frozenset(
    "alpha beta gamma delta epsilon theta lambda mu nu pi rho sigma tau phi chi psi omega "
    "Gamma Delta Theta Lambda Pi Sigma Phi Psi Omega frac sqrt binom mathbb mathcal mathrm text "
    "left right lvert rvert langle rangle cdot times pm mp div neq le leq ge geq in notin subset subseteq "
    "supset supseteq cup cap bigcup bigcap setminus emptyset varnothing land lor neg forall exists implies iff to mapsto "
    "rightarrow leftarrow leftrightarrow Rightarrow Leftarrow Leftrightarrow Longrightarrow longrightarrow "
    "sum prod lim log ln sin cos tan max min ldots cdots dots quad qquad circ equiv mod pmod mid nmid parallel perp "
    "cong sim approx propto infty overline underline vec lfloor rfloor lceil rceil operatorname".split()
)
_MATH_FRAGMENT = re.compile(r"\$([^$\n]{1,2000})\$")
_MATH_COMMAND = re.compile(r"\\([A-Za-z]+)")
_COMBINING_OVERLINE = re.compile(r"([A-Za-z0-9])\u0304")
_TEXT_REPLACEMENTS = str.maketrans({
    "–": "--", "‘": "'", "’": "'", "“": "``", "”": "''",
    "ﬁ": "fi", "ﬃ": "ffi",
})
_UNICODE_MATH_REPLACEMENTS = {
    "²": r"\ensuremath{{}^{2}}", "³": r"\ensuremath{{}^{3}}",
    "¹": r"\ensuremath{{}^{1}}", "⁰": r"\ensuremath{{}^{0}}",
    "·": r"\ensuremath{\cdot}", "×": r"\ensuremath{\times}",
    "Δ": r"\ensuremath{\Delta}", "Σ": r"\ensuremath{\Sigma}",
    "π": r"\ensuremath{\pi}", "→": r"\ensuremath{\to}",
    "↦": r"\ensuremath{\mapsto}", "↔": r"\ensuremath{\leftrightarrow}",
    "∈": r"\ensuremath{\in}", "−": r"\ensuremath{-}",
    "√": r"\ensuremath{\surd}", "∣": r"\ensuremath{\mid}",
    "∩": r"\ensuremath{\cap}", "∪": r"\ensuremath{\cup}",
    "≡": r"\ensuremath{\equiv}", "≠": r"\ensuremath{\neq}",
    "≤": r"\ensuremath{\le}", "≥": r"\ensuremath{\ge}",
    "≈": r"\ensuremath{\approx}", "∞": r"\ensuremath{\infty}",
    "⊂": r"\ensuremath{\subset}", "⊃": r"\ensuremath{\supset}",
    "⊆": r"\ensuremath{\subseteq}", "⊇": r"\ensuremath{\supseteq}",
    "∅": r"\ensuremath{\emptyset}", "∀": r"\ensuremath{\forall}",
    "∃": r"\ensuremath{\exists}", "¬": r"\ensuremath{\neg}",
    "∧": r"\ensuremath{\land}", "∨": r"\ensuremath{\lor}",
    "⇒": r"\ensuremath{\Rightarrow}", "⇔": r"\ensuremath{\Leftrightarrow}",
    "∥": r"\ensuremath{\parallel}", "⊥": r"\ensuremath{\perp}",
    "ℕ": r"\ensuremath{\mathbb{N}}", "ℤ": r"\ensuremath{\mathbb{Z}}",
    "ℚ": r"\ensuremath{\mathbb{Q}}", "ℝ": r"\ensuremath{\mathbb{R}}",
    "ℂ": r"\ensuremath{\mathbb{C}}", "◦": r"\ensuremath{\circ}",
}
# Preserve compatibility with verified source material that uses this alias.
# The normalized form is supported by the bounded offline resource set.
_OFFLINE_MATH_ALIASES = {r"\varnothing": r"\emptyset"}


def _plain(value: object | None) -> str:
    if value is None:
        return TO_BE_ANNOUNCED
    escaped = escape(str(value).translate(_TEXT_REPLACEMENTS))
    # Imported source material sometimes uses z̄/w̄ outside `$...$` fragments.
    # Only an ASCII base character can become this fixed trusted TeX form.
    escaped = _COMBINING_OVERLINE.sub(r"$\\overline{\1}$", escaped)
    for character, replacement in _UNICODE_MATH_REPLACEMENTS.items():
        escaped = escaped.replace(character, replacement)
    return escaped.replace("\n", r"\newline ")


def _math_safe(source: str) -> bool:
    if any(token in source for token in ("%", "#", "&", "~", "^^")):
        return False
    return all(command in _SAFE_MATH_COMMANDS for command in _MATH_COMMAND.findall(source))


def _offline_math(source: str) -> str:
    for original, replacement in _OFFLINE_MATH_ALIASES.items():
        source = source.replace(original, replacement)
    return source


def safe_question_text(value: object) -> str:
    """Render verified inline math while treating all non-whitelisted input as text."""
    source = str(value)
    result: list[str] = []
    cursor = 0
    for match in _MATH_FRAGMENT.finditer(source):
        result.append(_plain(source[cursor:match.start()]))
        math = _offline_math(match.group(1))
        result.append(f"${math}$" if _math_safe(math) else _plain(match.group(0)))
        cursor = match.end()
    result.append(_plain(source[cursor:]))
    return "".join(result)


def _current_questions(session: Session, exam: Exam) -> list[dict]:
    entries = list(exam.questions)
    ids = [entry.question_id for entry in entries]
    if not ids:
        raise HTTPException(422, "An exam needs at least one question to render")
    rows = session.scalars(
        select(Question)
        .where(Question.id.in_(ids))
        .options(selectinload(Question.options), selectinload(Question.topic))
    ).all()
    questions = {question.id: question for question in rows}
    if len(questions) != len(ids):
        raise HTTPException(422, "An exam question is no longer available")
    result = []
    for entry in entries:
        question = questions[entry.question_id]
        result.append({
            "question_id": entry.question_id,
            "position": entry.position,
            "points": entry.points,
            "title": question.title,
            "topic": {"name": question.topic.name, "slug": question.topic.slug},
            "response_type": question.response_type,
            "question_text": question.question_text,
            "expected_answer": question.expected_answer,
            "correct_boolean": question.correct_boolean,
            "explanation": question.explanation,
            "options": [
                {"text": option.text, "is_correct": option.is_correct, "position": option.position}
                for option in question.options
            ],
        })
    return result


def _snapshot_questions(exam: Exam) -> list[dict]:
    snapshot = exam.question_snapshot
    if not isinstance(snapshot, dict) or snapshot.get("version") != 1 or not isinstance(snapshot.get("questions"), list):
        raise HTTPException(422, "The finalized exam snapshot is invalid")
    questions = snapshot["questions"]
    required = {"question_id", "position", "points", "response_type", "question_text", "options"}
    if not questions or any(not isinstance(item, dict) or not required <= item.keys() for item in questions):
        raise HTTPException(422, "The finalized exam snapshot is incomplete")
    if any(not isinstance(item["points"], int) or item["points"] < 1 for item in questions):
        raise HTTPException(422, "The finalized exam snapshot has invalid points")
    return sorted(questions, key=lambda item: item["position"])


def _answer(item: dict) -> str:
    if item.get("expected_answer"):
        answer = r"\textbf{Reference answer:} " + safe_question_text(item["expected_answer"])
    elif item.get("correct_boolean") is not None:
        answer = r"\textbf{Correct answer:} " + ("True" if item["correct_boolean"] else "False")
    else:
        options = [safe_question_text(option.get("text", "")) for option in item.get("options", []) if isinstance(option, dict) and option.get("is_correct")]
        if not options:
            raise HTTPException(422, "A question has no valid answer for the answer key")
        answer = r"\textbf{Correct option(s):} " + "; ".join(options)
    if item.get("explanation"):
        answer += r"\par\textbf{Guidance:} " + safe_question_text(item["explanation"])
    return answer


def _blocks(questions: list[dict], answer_key: bool) -> str:
    lines = [r"\begin{enumerate}"]
    for item in questions:
        title = f" ({_plain(item['title'])})" if item.get("title") else ""
        lines.append(r"\item \textbf{" + str(item["points"]) + " points}" + title + r"\par " + safe_question_text(item["question_text"]))
        if answer_key:
            lines.append(_answer(item))
        elif item.get("response_type") == "FREE_RESPONSE":
            lines.append(r"\vspace{25mm}\hrule")
        else:
            lines.append(r"\vspace{8mm}")
    return "\n".join(lines + [r"\end{enumerate}"])


def render_exam_document(session: Session, exam_id: int, document_type: ExamDocumentType) -> str:
    exam = get_exam(session, exam_id)
    questions = _snapshot_questions(exam) if exam.status == "finalized" else _current_questions(session, exam)
    if exam.status not in {"draft", "finalized"}:
        raise HTTPException(422, "Exam status is invalid")
    configuration = session.get(AssessmentConfiguration, exam.assessment_configuration_id) if exam.assessment_configuration_id else None
    values = {
        "EXAM_TITLE": _plain(exam.title),
        "INSTRUCTIONS": safe_question_text(exam.instructions) if exam.instructions else "",
        "ASSESSMENT_CONTEXT": _plain(configuration.display_label) if configuration else "",
        "TOTAL_POINTS": str(sum(item["points"] for item in questions)),
        "QUESTION_BLOCKS": _blocks(questions, answer_key=False),
        "ANSWER_KEY_BLOCKS": _blocks(questions, answer_key=True),
    }
    template = (Path(__file__).parent / "templates" / _TEMPLATES[document_type]).read_text(encoding="utf-8")
    return re.sub(r"@@([A-Z_]+)@@", lambda match: values[match.group(1)], template)
