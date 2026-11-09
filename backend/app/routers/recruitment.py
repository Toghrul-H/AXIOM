from datetime import datetime, timezone
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.auth import get_current_user, manager_user, student_user
from app.auth_models import User
from app.database import get_session
from app.recruitment_models import DemonstratorApplication, DemonstratorApplicationAnswer, DemonstratorQuestion, DemonstratorVacancy, RecruitmentNotification
from app.recruitment_schemas import ApplicationRead, ApplicationStatusUpdate, ApplicationWrite, NotificationRead, QuestionnaireQuestionRead, QuestionnaireUpdate, StaffVacancyRead, VacancyRead, VacancyWrite

router = APIRouter(tags=["Demonstrator recruitment"])
DB = Annotated[Session, Depends(get_session)]
Student = Annotated[User, Depends(student_user)]
Manager = Annotated[User, Depends(manager_user)]
Identity = Annotated[User, Depends(get_current_user)]
Id = Annotated[int, Path(gt=0)]

STATUSES = ("SUBMITTED", "UNDER_REVIEW", "ACCEPTED", "REJECTED", "WITHDRAWN")
STAFF_TRANSITIONS = {"SUBMITTED": {"UNDER_REVIEW", "ACCEPTED", "REJECTED"}, "UNDER_REVIEW": {"ACCEPTED", "REJECTED"}}


def now() -> datetime:
    return datetime.now(timezone.utc)


def application_open(vacancy: DemonstratorVacancy) -> bool:
    point = now()
    return vacancy.state == "OPEN" and vacancy.available_positions > 0 and (vacancy.opens_at is None or vacancy.opens_at <= point) and (vacancy.closes_at is None or point < vacancy.closes_at)


def status_summaries(session: Session, vacancy_ids: list[int]) -> dict[int, dict[str, int]]:
    summaries = {vacancy_id: {status: 0 for status in STATUSES} for vacancy_id in vacancy_ids}
    if not vacancy_ids:
        return summaries
    for vacancy_id, status, count in session.execute(select(DemonstratorApplication.vacancy_id, DemonstratorApplication.status, func.count(DemonstratorApplication.id)).where(DemonstratorApplication.vacancy_id.in_(vacancy_ids)).group_by(DemonstratorApplication.vacancy_id, DemonstratorApplication.status)):
        summaries[vacancy_id][status] = count
    return summaries


def questions_for(session: Session, vacancy_id: int) -> list[DemonstratorQuestion]:
    return list(session.scalars(select(DemonstratorQuestion).where(DemonstratorQuestion.vacancy_id == vacancy_id).order_by(DemonstratorQuestion.display_order, DemonstratorQuestion.id)))


def question_read(question: DemonstratorQuestion) -> dict:
    return {"id": question.id, "title": question.title, "question_type": question.question_type, "required": question.required, "options": question.options, "display_order": question.display_order}


def questionnaire_locked(session: Session, vacancy_id: int) -> bool:
    return bool(session.scalar(select(DemonstratorApplication.id).where(DemonstratorApplication.vacancy_id == vacancy_id).limit(1)))


def vacancy_read(session: Session, vacancy: DemonstratorVacancy, counts: dict[str, int]) -> dict:
    return {name: getattr(vacancy, name) for name in ("id", "course_name", "semester", "available_positions", "description", "responsibilities", "opens_at", "closes_at", "state")} | {"applicant_count": sum(count for status, count in counts.items() if status != "WITHDRAWN"), "application_open": application_open(vacancy), "questionnaire": [question_read(question) for question in questions_for(session, vacancy.id)]}


def staff_vacancy_read(session: Session, vacancy: DemonstratorVacancy, counts: dict[str, int]) -> dict:
    return vacancy_read(session, vacancy, counts) | {"status_counts": counts, "accepted_count": counts["ACCEPTED"], "remaining_positions": max(vacancy.available_positions - counts["ACCEPTED"], 0), "questionnaire_locked": questionnaire_locked(session, vacancy.id)}


def vacancy_or_404(session: Session, vacancy_id: int) -> DemonstratorVacancy:
    vacancy = session.get(DemonstratorVacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(404, "Demonstrator vacancy not found")
    return vacancy


def publish_notifications(session: Session, vacancy: DemonstratorVacancy) -> None:
    users = session.scalars(select(User.id).where(User.role == "STUDENT", User.is_active.is_(True), User.email_verified.is_(True), User.is_legacy.is_(False))).all()
    for user_id in users:
        exists = session.scalar(select(RecruitmentNotification.id).where(RecruitmentNotification.user_id == user_id, RecruitmentNotification.vacancy_id == vacancy.id, RecruitmentNotification.kind == "VACANCY_OPEN"))
        if not exists:
            session.add(RecruitmentNotification(user_id=user_id, vacancy_id=vacancy.id, title="New Demonstrator Opportunity", body=f"{vacancy.course_name} is looking for {vacancy.available_positions} demonstrator(s). Applications are now open.", link="/student/demonstrator-opportunities"))


def notify_application_status(session: Session, application: DemonstratorApplication, vacancy: DemonstratorVacancy) -> None:
    kind = f"APPLICATION_{application.status}"
    if session.scalar(select(RecruitmentNotification.id).where(RecruitmentNotification.user_id == application.user_id, RecruitmentNotification.vacancy_id == vacancy.id, RecruitmentNotification.kind == kind)):
        return
    wording = {"UNDER_REVIEW": "is now under review.", "ACCEPTED": "has been accepted.", "REJECTED": "has been declined."}[application.status]
    session.add(RecruitmentNotification(user_id=application.user_id, vacancy_id=vacancy.id, kind=kind, title="Demonstrator Application Update", body=f"Your application for {vacancy.course_name} {wording}", link="/student/demonstrator-opportunities"))


def validate_custom_answers(questions: list[DemonstratorQuestion], answers: dict[int, object]) -> None:
    expected = {question.id for question in questions}
    if set(answers) - expected:
        raise HTTPException(422, "Unknown questionnaire answer")
    for question in questions:
        answer = answers.get(question.id)
        missing = answer is None or answer == "" or answer == []
        if question.required and missing:
            raise HTTPException(422, f"An answer is required for: {question.title}")
        if missing:
            continue
        if question.question_type in {"SHORT_TEXT", "LONG_TEXT"}:
            if not isinstance(answer, str) or len(answer) > 10000:
                raise HTTPException(422, f"Invalid answer for: {question.title}")
        elif question.question_type == "YES_NO":
            if not isinstance(answer, bool):
                raise HTTPException(422, f"Invalid answer for: {question.title}")
        elif question.question_type == "SINGLE_CHOICE":
            if not isinstance(answer, str) or answer not in (question.options or []):
                raise HTTPException(422, f"Invalid answer for: {question.title}")
        elif question.question_type == "MULTIPLE_CHOICE":
            if not isinstance(answer, list) or not answer or any(not isinstance(value, str) or value not in (question.options or []) for value in answer) or len(set(answer)) != len(answer):
                raise HTTPException(422, f"Invalid answer for: {question.title}")


def application_read(session: Session, item: DemonstratorApplication) -> dict:
    answers = list(session.scalars(select(DemonstratorApplicationAnswer).where(DemonstratorApplicationAnswer.application_id == item.id).order_by(DemonstratorApplicationAnswer.display_order)))
    def optional(value: str | None) -> str | None:
        return None if value in {None, "", "Not provided"} else value
    return {"id": item.id, "vacancy_id": item.vacancy_id, "full_name": item.full_name, "neptun_code": item.neptun_code, "lecture_grade": item.lecture_grade, "practice_grade": item.practice_grade, "legacy_final_grade": item.final_grade, "legacy_completion_semester": optional(item.completion_semester), "practice_teacher": optional(item.practice_teacher), "motivation": optional(item.motivation), "weekly_availability": item.weekly_availability, "preferred_responsibilities": item.preferred_responsibilities, "relevant_experience": optional(item.teaching_experience), "additional_comments": item.additional_information, "custom_answers": [{"question_id": answer.question_id, "question_title": answer.question_title, "question_type": answer.question_type, "answer": answer.answer, "display_order": answer.display_order} for answer in answers], "status": item.status, "submitted_at": item.submitted_at, "decision_at": item.decision_at}


@router.get("/demonstrator-vacancies", response_model=list[VacancyRead])
def student_vacancies(session: DB, actor: Student):
    vacancies = list(session.scalars(select(DemonstratorVacancy).where(DemonstratorVacancy.state == "OPEN").order_by(DemonstratorVacancy.created_at.desc())))
    summaries = status_summaries(session, [item.id for item in vacancies])
    return [vacancy_read(session, item, summaries[item.id]) for item in vacancies]


@router.post("/demonstrator-vacancies/{vacancy_id}/applications", response_model=ApplicationRead, status_code=201)
def apply(vacancy_id: Id, payload: ApplicationWrite, session: DB, actor: Student):
    vacancy = vacancy_or_404(session, vacancy_id)
    if not application_open(vacancy):
        raise HTTPException(409, "Applications are not open for this vacancy")
    questions = questions_for(session, vacancy.id)
    validate_custom_answers(questions, payload.custom_answers)
    values = payload.model_dump(exclude={"custom_answers", "relevant_experience", "additional_comments"})
    application = DemonstratorApplication(vacancy_id=vacancy.id, user_id=actor.id, final_grade=None, completion_semester="Not provided", teaching_experience=payload.relevant_experience or "Not provided", responsibility_interest="; ".join(payload.preferred_responsibilities), additional_information=payload.additional_comments, **values)
    session.add(application)
    try:
        session.flush()
        for question in questions:
            answer = payload.custom_answers.get(question.id)
            if answer is not None and answer != "" and answer != []:
                session.add(DemonstratorApplicationAnswer(application_id=application.id, question_id=question.id, question_title=question.title, question_type=question.question_type, answer=answer, display_order=question.display_order))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "You have already applied for this vacancy") from None
    session.refresh(application)
    return application_read(session, application)


@router.get("/demonstrator-applications/me", response_model=list[ApplicationRead])
def my_applications(session: DB, actor: Student):
    return [application_read(session, item) for item in session.scalars(select(DemonstratorApplication).where(DemonstratorApplication.user_id == actor.id).order_by(DemonstratorApplication.submitted_at.desc()))]


@router.post("/demonstrator-applications/{application_id}/withdraw", response_model=ApplicationRead)
def withdraw(application_id: Id, session: DB, actor: Student):
    application = session.get(DemonstratorApplication, application_id)
    if application is None or application.user_id != actor.id:
        raise HTTPException(404, "Application not found")
    if application.status not in {"SUBMITTED", "UNDER_REVIEW"}:
        raise HTTPException(409, "This application can no longer be withdrawn")
    application.status = "WITHDRAWN"; session.commit(); session.refresh(application)
    return application_read(session, application)


@router.get("/notifications/recruitment", response_model=list[NotificationRead])
def notifications(session: DB, actor: Identity, limit: Annotated[int, Query(ge=1, le=50)] = 10):
    return list(session.scalars(select(RecruitmentNotification).where(RecruitmentNotification.user_id == actor.id).order_by(RecruitmentNotification.created_at.desc()).limit(limit)))


@router.post("/staff/demonstrator-vacancies", response_model=StaffVacancyRead, status_code=201)
def create_vacancy(payload: VacancyWrite, session: DB, actor: Manager):
    vacancy = DemonstratorVacancy(**payload.model_dump(), created_by_id=actor.id, published_at=now() if payload.state == "OPEN" else None)
    session.add(vacancy); session.flush()
    if payload.state == "OPEN": publish_notifications(session, vacancy)
    session.commit()
    return staff_vacancy_read(session, vacancy, {status: 0 for status in STATUSES})


@router.patch("/staff/demonstrator-vacancies/{vacancy_id}", response_model=StaffVacancyRead)
def update_vacancy(vacancy_id: Id, payload: VacancyWrite, session: DB, actor: Manager):
    vacancy = vacancy_or_404(session, vacancy_id); was_open = vacancy.state == "OPEN"
    for key, value in payload.model_dump().items(): setattr(vacancy, key, value)
    if vacancy.state == "OPEN" and not was_open:
        vacancy.published_at = now(); publish_notifications(session, vacancy)
    session.commit()
    return staff_vacancy_read(session, vacancy, status_summaries(session, [vacancy.id])[vacancy.id])


@router.get("/staff/demonstrator-vacancies", response_model=list[StaffVacancyRead])
def staff_vacancies(session: DB, actor: Manager):
    vacancies = list(session.scalars(select(DemonstratorVacancy).order_by(DemonstratorVacancy.created_at.desc())))
    summaries = status_summaries(session, [item.id for item in vacancies])
    return [staff_vacancy_read(session, item, summaries[item.id]) for item in vacancies]


@router.put("/staff/demonstrator-vacancies/{vacancy_id}/questionnaire", response_model=list[QuestionnaireQuestionRead])
def update_questionnaire(vacancy_id: Id, payload: QuestionnaireUpdate, session: DB, actor: Manager):
    vacancy_or_404(session, vacancy_id)
    if questionnaire_locked(session, vacancy_id):
        raise HTTPException(409, "The questionnaire is locked because applications exist")
    session.query(DemonstratorQuestion).filter(DemonstratorQuestion.vacancy_id == vacancy_id).delete(synchronize_session=False)
    questions = [DemonstratorQuestion(vacancy_id=vacancy_id, title=item.title.strip(), question_type=item.question_type, required=item.required, options=[option.strip() for option in item.options] if item.options else None, display_order=index) for index, item in enumerate(payload.questions)]
    session.add_all(questions); session.commit()
    return [question_read(question) for question in questions]


@router.get("/staff/demonstrator-vacancies/{vacancy_id}/applications", response_model=list[ApplicationRead])
def applications(vacancy_id: Id, session: DB, actor: Manager, offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    vacancy_or_404(session, vacancy_id)
    return [application_read(session, item) for item in session.scalars(select(DemonstratorApplication).where(DemonstratorApplication.vacancy_id == vacancy_id).order_by(DemonstratorApplication.submitted_at.desc()).offset(offset).limit(limit))]


@router.patch("/staff/demonstrator-vacancies/{vacancy_id}/applications/{application_id}", response_model=ApplicationRead)
def update_application_status(vacancy_id: Id, application_id: Id, payload: ApplicationStatusUpdate, session: DB, actor: Manager):
    vacancy = session.execute(select(DemonstratorVacancy).where(DemonstratorVacancy.id == vacancy_id).with_for_update()).scalar_one_or_none()
    if vacancy is None: raise HTTPException(404, "Demonstrator vacancy not found")
    application = session.get(DemonstratorApplication, application_id)
    if application is None or application.vacancy_id != vacancy.id: raise HTTPException(404, "Application not found")
    if payload.status not in STAFF_TRANSITIONS.get(application.status, set()): raise HTTPException(409, "Invalid application status transition")
    if payload.status == "ACCEPTED":
        accepted = session.scalar(select(func.count(DemonstratorApplication.id)).where(DemonstratorApplication.vacancy_id == vacancy.id, DemonstratorApplication.status == "ACCEPTED")) or 0
        if accepted >= vacancy.available_positions: raise HTTPException(409, "All demonstrator positions have already been accepted")
    application.status = payload.status
    if payload.status in {"ACCEPTED", "REJECTED"}: application.decision_at = now(); application.decision_by_id = actor.id
    notify_application_status(session, application, vacancy); session.commit(); session.refresh(application)
    return application_read(session, application)


@router.get("/staff/demonstrator-vacancies/{vacancy_id}/applications/{application_id}", response_model=ApplicationRead)
def application_detail(vacancy_id: Id, application_id: Id, session: DB, actor: Manager):
    item = session.get(DemonstratorApplication, application_id)
    if item is None or item.vacancy_id != vacancy_id: raise HTTPException(404, "Application not found")
    return application_read(session, item)


def safe_cell(value: object | None) -> str:
    text = "" if value is None else "; ".join(value) if isinstance(value, list) else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


@router.get("/staff/demonstrator-vacancies/{vacancy_id}/applications.xlsx")
def export_applications(vacancy_id: Id, session: DB, actor: Manager):
    vacancy_or_404(session, vacancy_id)
    questions = questions_for(session, vacancy_id); decision_maker = aliased(User)
    rows = session.execute(select(DemonstratorApplication, decision_maker.email).outerjoin(decision_maker, DemonstratorApplication.decision_by_id == decision_maker.id).where(DemonstratorApplication.vacancy_id == vacancy_id).order_by(DemonstratorApplication.submitted_at)).all()
    book = Workbook(write_only=True); sheet = book.create_sheet("Applicants")
    fixed = ["Applicant full name", "Neptun code", "Lecture grade", "Practice grade", "Practice teacher", "Weekly availability (hours)", "Motivation", "Preferred responsibilities", "Relevant experience", "Additional comments", "Application status", "Decision timestamp", "Decision maker", "Secure questionnaire reference"]
    sheet.append(fixed + [f"Custom: {question.title}" for question in questions])
    for item, decision_maker_email in rows:
        answers = {answer.question_id: answer.answer for answer in session.scalars(select(DemonstratorApplicationAnswer).where(DemonstratorApplicationAnswer.application_id == item.id))}
        base = [item.full_name, item.neptun_code, item.lecture_grade or "Not provided", item.practice_grade or "Not provided", item.practice_teacher or "Not provided", item.weekly_availability if item.weekly_availability is not None else "Not provided", item.motivation or "Not provided", item.preferred_responsibilities or "Not provided", item.teaching_experience if item.teaching_experience not in {None, "", "Not provided"} else "Not provided", item.additional_information or "Not provided", item.status, item.decision_at.isoformat() if item.decision_at else "", decision_maker_email or "", f"/staff/demonstrator-vacancies/{vacancy_id}/applications/{item.id}"]
        sheet.append([safe_cell(value) for value in base + [answers.get(question.id, "Not provided") for question in questions]])
    payload = BytesIO(); book.save(payload); payload.seek(0)
    return StreamingResponse(payload, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="axiom-demonstrator-vacancy-{vacancy_id}.xlsx"', "Cache-Control": "no-store"})
