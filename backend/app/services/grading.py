"""Stateless objective checks; never creates student attempts or scores."""
from fastapi import HTTPException
from typing import Protocol, Sequence
from app.schemas import AnswerCheck, AnswerFeedback


class GradableOption(Protocol):
    id: int
    is_correct: bool


class GradableQuestion(Protocol):
    """Shared by bank questions and immutable attempt snapshots."""
    response_type: str
    expected_answer: str | None
    correct_boolean: bool | None
    explanation: str | None

    @property
    def options(self) -> Sequence[GradableOption]: ...


def check_answer(question: GradableQuestion, answer: AnswerCheck) -> AnswerFeedback:
    correct_ids = [option.id for option in question.options if option.is_correct]
    is_correct = None
    auto_gradable = question.response_type != "FREE_RESPONSE"
    if question.response_type in {"SINGLE_CHOICE", "MULTIPLE_SELECT"}:
        if answer.boolean_answer is not None or answer.free_response is not None:
            raise HTTPException(status_code=422, detail="Submit only selected_option_ids for choice questions")
        if question.response_type == "SINGLE_CHOICE" and len(answer.selected_option_ids) != 1:
            raise HTTPException(status_code=422, detail="Select exactly one option")
        if not set(answer.selected_option_ids).issubset({o.id for o in question.options}):
            raise HTTPException(status_code=422, detail="Selected option does not belong to this question")
        is_correct = set(answer.selected_option_ids) == set(correct_ids)
    elif question.response_type == "TRUE_FALSE":
        if answer.boolean_answer is None or answer.selected_option_ids or answer.free_response is not None:
            raise HTTPException(status_code=422, detail="Submit a boolean_answer only")
        is_correct = answer.boolean_answer == question.correct_boolean
    else:
        if answer.selected_option_ids or answer.boolean_answer is not None:
            raise HTTPException(status_code=422, detail="Submit free_response text for free-response questions")
    return AnswerFeedback(
        auto_gradable=auto_gradable, is_correct=is_correct,
        correct_option_ids=correct_ids, correct_boolean=question.correct_boolean,
        expected_answer=question.expected_answer, explanation=question.explanation,
        message="Objective answer check for learning only." if auto_gradable else "Free responses are not automatically graded. Compare your reasoning with the reference solution.",
    )
