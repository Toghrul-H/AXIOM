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
from app.recruitment_models import DemonstratorApplication, DemonstratorVacancy, RecruitmentNotification
from app.recruitment_schemas import ApplicationRead, ApplicationStatusUpdate, ApplicationWrite, NotificationRead, StaffVacancyRead, VacancyRead, VacancyWrite

router = APIRouter(tags=["Demonstrator recruitment"])
DB = Annotated[Session, Depends(get_session)]
Student = Annotated[User, Depends(student_user)]
Manager = Annotated[User, Depends(manager_user)]
Identity = Annotated[User, Depends(get_current_user)]
Id = Annotated[int, Path(gt=0)]

STATUSES = ("SUBMITTED", "UNDER_REVIEW", "ACCEPTED", "REJECTED", "WITHDRAWN")
STAFF_TRANSITIONS = {
    "SUBMITTED": {"UNDER_REVIEW", "ACCEPTED", "REJECTED"},
    "UNDER_REVIEW": {"ACCEPTED", "REJECTED"},
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def application_open(vacancy: DemonstratorVacancy) -> bool:
    point = now()
    return (
        vacancy.state == "OPEN"
        and vacancy.available_positions > 0
        and (vacancy.opens_at is None or vacancy.opens_at <= point)
        and (vacancy.closes_at is None or point < vacancy.closes_at)
    )


def status_summaries(session: Session, vacancy_ids: list[int]) -> dict[int, dict[str, int]]:
    summaries = {vacancy_id: {status: 0 for status in STATUSES} for vacancy_id in vacancy_ids}
    if not vacancy_ids:
        return summaries
    rows = session.execute(
        select(DemonstratorApplication.vacancy_id, DemonstratorApplication.status, func.count(DemonstratorApplication.id))
        .where(DemonstratorApplication.vacancy_id.in_(vacancy_ids))
        .group_by(DemonstratorApplication.vacancy_id, DemonstratorApplication.status)
    )
    for vacancy_id, status, count in rows:
        summaries[vacancy_id][status] = count
    return summaries


def vacancy_read(vacancy: DemonstratorVacancy, counts: dict[str, int]) -> dict:
    return {
        name: getattr(vacancy, name)
        for name in ("id", "course_name", "semester", "available_positions", "description", "responsibilities", "opens_at", "closes_at", "state")
    } | {
        "applicant_count": sum(count for status, count in counts.items() if status != "WITHDRAWN"),
        "application_open": application_open(vacancy),
    }


def staff_vacancy_read(vacancy: DemonstratorVacancy, counts: dict[str, int]) -> dict:
    accepted = counts["ACCEPTED"]
    return vacancy_read(vacancy, counts) | {
        "status_counts": counts,
        "accepted_count": accepted,
        "remaining_positions": max(vacancy.available_positions - accepted, 0),
    }


def vacancy_or_404(session: Session, vacancy_id: int) -> DemonstratorVacancy:
    vacancy = session.get(DemonstratorVacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(404, "Demonstrator vacancy not found")
    return vacancy


def publish_notifications(session: Session, vacancy: DemonstratorVacancy) -> None:
    students = session.scalars(select(User.id).where(User.role == "STUDENT", User.is_active.is_(True), User.email_verified.is_(True), User.is_legacy.is_(False))).all()
    for user_id in students:
        exists = session.scalar(select(RecruitmentNotification.id).where(RecruitmentNotification.user_id == user_id, RecruitmentNotification.vacancy_id == vacancy.id, RecruitmentNotification.kind == "VACANCY_OPEN"))
        if not exists:
            session.add(RecruitmentNotification(user_id=user_id, vacancy_id=vacancy.id, title="New Demonstrator Opportunity", body=f"{vacancy.course_name} is looking for {vacancy.available_positions} demonstrator(s). Applications are now open.", link="/student/demonstrator-opportunities"))


def notify_application_status(session: Session, application: DemonstratorApplication, vacancy: DemonstratorVacancy) -> None:
    kind = f"APPLICATION_{application.status}"
    exists = session.scalar(select(RecruitmentNotification.id).where(RecruitmentNotification.user_id == application.user_id, RecruitmentNotification.vacancy_id == vacancy.id, RecruitmentNotification.kind == kind))
    if exists:
        return
    wording = {
        "UNDER_REVIEW": "is now under review.",
        "ACCEPTED": "has been accepted.",
        "REJECTED": "has been declined.",
    }[application.status]
    session.add(RecruitmentNotification(user_id=application.user_id, vacancy_id=vacancy.id, kind=kind, title="Demonstrator Application Update", body=f"Your application for {vacancy.course_name} {wording}", link="/student/demonstrator-opportunities"))


@router.get("/demonstrator-vacancies", response_model=list[VacancyRead])
def student_vacancies(session: DB, actor: Student):
    vacancies = list(session.scalars(select(DemonstratorVacancy).where(DemonstratorVacancy.state == "OPEN").order_by(DemonstratorVacancy.created_at.desc())))
    summaries = status_summaries(session, [item.id for item in vacancies])
    return [vacancy_read(item, summaries[item.id]) for item in vacancies]


@router.post("/demonstrator-vacancies/{vacancy_id}/applications", response_model=ApplicationRead, status_code=201)
def apply(vacancy_id: Id, payload: ApplicationWrite, session: DB, actor: Student):
    vacancy = vacancy_or_404(session, vacancy_id)
    if not application_open(vacancy):
        raise HTTPException(409, "Applications are not open for this vacancy")
    application = DemonstratorApplication(vacancy_id=vacancy.id, user_id=actor.id, **payload.model_dump())
    session.add(application)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "You have already applied for this vacancy") from None
    session.refresh(application)
    return application


@router.get("/demonstrator-applications/me", response_model=list[ApplicationRead])
def my_applications(session: DB, actor: Student):
    return list(session.scalars(select(DemonstratorApplication).where(DemonstratorApplication.user_id == actor.id).order_by(DemonstratorApplication.submitted_at.desc())))


@router.post("/demonstrator-applications/{application_id}/withdraw", response_model=ApplicationRead)
def withdraw(application_id: Id, session: DB, actor: Student):
    application = session.get(DemonstratorApplication, application_id)
    if application is None or application.user_id != actor.id:
        raise HTTPException(404, "Application not found")
    if application.status not in {"SUBMITTED", "UNDER_REVIEW"}:
        raise HTTPException(409, "This application can no longer be withdrawn")
    application.status = "WITHDRAWN"
    session.commit()
    session.refresh(application)
    return application


@router.get("/notifications/recruitment", response_model=list[NotificationRead])
def notifications(session: DB, actor: Identity, limit: Annotated[int, Query(ge=1, le=50)] = 10):
    return list(session.scalars(select(RecruitmentNotification).where(RecruitmentNotification.user_id == actor.id).order_by(RecruitmentNotification.created_at.desc()).limit(limit)))


@router.post("/staff/demonstrator-vacancies", response_model=StaffVacancyRead, status_code=201)
def create_vacancy(payload: VacancyWrite, session: DB, actor: Manager):
    vacancy = DemonstratorVacancy(**payload.model_dump(), created_by_id=actor.id, published_at=now() if payload.state == "OPEN" else None)
    session.add(vacancy)
    session.flush()
    if payload.state == "OPEN":
        publish_notifications(session, vacancy)
    session.commit()
    return staff_vacancy_read(vacancy, {status: 0 for status in STATUSES})


@router.patch("/staff/demonstrator-vacancies/{vacancy_id}", response_model=StaffVacancyRead)
def update_vacancy(vacancy_id: Id, payload: VacancyWrite, session: DB, actor: Manager):
    vacancy = vacancy_or_404(session, vacancy_id)
    was_open = vacancy.state == "OPEN"
    for key, value in payload.model_dump().items():
        setattr(vacancy, key, value)
    if vacancy.state == "OPEN" and not was_open:
        vacancy.published_at = now()
        publish_notifications(session, vacancy)
    session.commit()
    return staff_vacancy_read(vacancy, status_summaries(session, [vacancy.id])[vacancy.id])


@router.get("/staff/demonstrator-vacancies", response_model=list[StaffVacancyRead])
def staff_vacancies(session: DB, actor: Manager):
    vacancies = list(session.scalars(select(DemonstratorVacancy).order_by(DemonstratorVacancy.created_at.desc())))
    summaries = status_summaries(session, [item.id for item in vacancies])
    return [staff_vacancy_read(item, summaries[item.id]) for item in vacancies]


@router.get("/staff/demonstrator-vacancies/{vacancy_id}/applications", response_model=list[ApplicationRead])
def applications(vacancy_id: Id, session: DB, actor: Manager, offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=100)] = 20):
    vacancy_or_404(session, vacancy_id)
    return list(session.scalars(select(DemonstratorApplication).where(DemonstratorApplication.vacancy_id == vacancy_id).order_by(DemonstratorApplication.submitted_at.desc()).offset(offset).limit(limit)))


@router.patch("/staff/demonstrator-vacancies/{vacancy_id}/applications/{application_id}", response_model=ApplicationRead)
def update_application_status(vacancy_id: Id, application_id: Id, payload: ApplicationStatusUpdate, session: DB, actor: Manager):
    vacancy = session.execute(select(DemonstratorVacancy).where(DemonstratorVacancy.id == vacancy_id).with_for_update()).scalar_one_or_none()
    if vacancy is None:
        raise HTTPException(404, "Demonstrator vacancy not found")
    application = session.get(DemonstratorApplication, application_id)
    if application is None or application.vacancy_id != vacancy.id:
        raise HTTPException(404, "Application not found")
    if payload.status not in STAFF_TRANSITIONS.get(application.status, set()):
        raise HTTPException(409, "Invalid application status transition")
    if payload.status == "ACCEPTED":
        accepted = session.scalar(select(func.count(DemonstratorApplication.id)).where(DemonstratorApplication.vacancy_id == vacancy.id, DemonstratorApplication.status == "ACCEPTED")) or 0
        if accepted >= vacancy.available_positions:
            raise HTTPException(409, "All demonstrator positions have already been accepted")
    application.status = payload.status
    if payload.status in {"ACCEPTED", "REJECTED"}:
        application.decision_at = now()
        application.decision_by_id = actor.id
    notify_application_status(session, application, vacancy)
    session.commit()
    session.refresh(application)
    return application


@router.get("/staff/demonstrator-vacancies/{vacancy_id}/applications/{application_id}", response_model=ApplicationRead)
def application_detail(vacancy_id: Id, application_id: Id, session: DB, actor: Manager):
    item = session.get(DemonstratorApplication, application_id)
    if item is None or item.vacancy_id != vacancy_id:
        raise HTTPException(404, "Application not found")
    return item


def safe_cell(value: object | None) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


@router.get("/staff/demonstrator-vacancies/{vacancy_id}/applications.xlsx")
def export_applications(vacancy_id: Id, session: DB, actor: Manager):
    vacancy_or_404(session, vacancy_id)
    decision_maker = aliased(User)
    rows = session.execute(select(DemonstratorApplication, decision_maker.email).outerjoin(decision_maker, DemonstratorApplication.decision_by_id == decision_maker.id).where(DemonstratorApplication.vacancy_id == vacancy_id).order_by(DemonstratorApplication.submitted_at)).all()
    book = Workbook(write_only=True)
    sheet = book.create_sheet("Applicants")
    sheet.append(["Applicant full name", "Neptun code", "Final grade", "Practice teacher", "Completion semester", "Submitted at", "Application status", "Decision timestamp", "Decision maker", "Secure questionnaire reference"])
    for item, decision_maker_email in rows:
        sheet.append([safe_cell(item.full_name), safe_cell(item.neptun_code), safe_cell(item.final_grade), safe_cell(item.practice_teacher), safe_cell(item.completion_semester), item.submitted_at.isoformat(), item.status, item.decision_at.isoformat() if item.decision_at else "", safe_cell(decision_maker_email), f"/staff/demonstrator-vacancies/{vacancy_id}/applications/{item.id}"])
    payload = BytesIO()
    book.save(payload)
    payload.seek(0)
    return StreamingResponse(payload, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="axiom-demonstrator-vacancy-{vacancy_id}.xlsx"', "Cache-Control": "no-store"})
