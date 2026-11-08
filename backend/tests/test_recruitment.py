from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth_models import User
from app.database import Base
from app.recruitment_models import DemonstratorApplication, DemonstratorVacancy, RecruitmentNotification
from app.recruitment_schemas import ApplicationStatusUpdate
from app.routers.recruitment import application_open, publish_notifications, safe_cell, status_summaries, update_application_status, withdraw


def setup():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    lecturer = User(email="lecturer@example.com", password_hash="x", role="LECTURER", email_verified=True)
    student = User(email="student@example.com", password_hash="x", role="STUDENT", email_verified=True)
    other = User(email="other@example.com", password_hash="x", role="STUDENT", email_verified=True)
    session.add_all((lecturer, student, other)); session.flush()
    vacancy = DemonstratorVacancy(course_name="DMI", semester="Spring 2027", available_positions=1, description="Teach", responsibilities="Support", state="OPEN", created_by_id=lecturer.id)
    session.add(vacancy); session.flush()
    application = DemonstratorApplication(vacancy_id=vacancy.id, user_id=student.id, full_name="Student", neptun_code="ABC123", final_grade="5", practice_teacher="Teacher", completion_semester="Spring", motivation="A detailed motivation", teaching_experience="None", responsibility_interest="Teaching")
    other_application = DemonstratorApplication(vacancy_id=vacancy.id, user_id=other.id, full_name="Other", neptun_code="DEF456", final_grade="4", practice_teacher="Teacher", completion_semester="Spring", motivation="Another detailed motivation", teaching_experience="None", responsibility_interest="Teaching")
    session.add_all((application, other_application)); session.commit()
    return session, lecturer, student, other, vacancy, application, other_application


def test_status_lifecycle_notifications_and_summary():
    session, lecturer, _, _, vacancy, application, _ = setup()
    updated = update_application_status(vacancy.id, application.id, ApplicationStatusUpdate(status="UNDER_REVIEW"), session, lecturer)
    assert updated.status == "UNDER_REVIEW"
    updated = update_application_status(vacancy.id, application.id, ApplicationStatusUpdate(status="ACCEPTED"), session, lecturer)
    assert updated.status == "ACCEPTED" and updated.decision_by_id == lecturer.id and updated.decision_at
    assert [notification.kind for notification in session.scalars(select(RecruitmentNotification).where(RecruitmentNotification.user_id == application.user_id)).all()] == ["APPLICATION_UNDER_REVIEW", "APPLICATION_ACCEPTED"]
    summary = status_summaries(session, [vacancy.id])[vacancy.id]
    assert summary["ACCEPTED"] == 1 and summary["SUBMITTED"] == 1 and summary["WITHDRAWN"] == 0
    with pytest.raises(HTTPException) as error:
        update_application_status(vacancy.id, application.id, ApplicationStatusUpdate(status="ACCEPTED"), session, lecturer)
    assert error.value.status_code == 409
    session.close()


def test_capacity_invalid_transition_and_withdrawal_ownership():
    session, lecturer, student, other, vacancy, application, other_application = setup()
    update_application_status(vacancy.id, application.id, ApplicationStatusUpdate(status="ACCEPTED"), session, lecturer)
    with pytest.raises(HTTPException) as error:
        update_application_status(vacancy.id, other_application.id, ApplicationStatusUpdate(status="ACCEPTED"), session, lecturer)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        withdraw(other_application.id, session, student)
    assert error.value.status_code == 404
    withdrawn = withdraw(other_application.id, session, other)
    assert withdrawn.status == "WITHDRAWN"
    with pytest.raises(HTTPException) as error:
        withdraw(application.id, session, student)
    assert error.value.status_code == 409
    session.close()


def test_notification_deduplication_formula_safety_and_open_window():
    session, lecturer, student, _, vacancy, _, _ = setup()
    publish_notifications(session, vacancy); publish_notifications(session, vacancy); session.commit()
    assert len(session.scalars(select(RecruitmentNotification).where(RecruitmentNotification.user_id == student.id, RecruitmentNotification.kind == "VACANCY_OPEN")).all()) == 1
    assert safe_cell("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    point = datetime.now(timezone.utc)
    vacancy.opens_at = point - timedelta(minutes=1); vacancy.closes_at = point + timedelta(minutes=1)
    assert application_open(vacancy)
    vacancy.available_positions = 0
    assert not application_open(vacancy)
    session.close()
