from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth_models import User
from app.database import Base
from app.recruitment_models import DemonstratorApplication, DemonstratorVacancy, RecruitmentNotification
from app.routers.recruitment import application_open, publish_notifications, safe_cell


def test_recruitment_notification_deduplication_and_formula_safety():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        student = User(email="student@example.com", password_hash="x", role="STUDENT", email_verified=True)
        lecturer = User(email="lecturer@example.com", password_hash="x", role="LECTURER", email_verified=True)
        session.add_all((student, lecturer)); session.flush()
        vacancy = DemonstratorVacancy(course_name="DMI", semester="Spring 2027", available_positions=1, description="Teach", responsibilities="Support", state="OPEN", created_by_id=lecturer.id)
        session.add(vacancy); session.flush()
        publish_notifications(session, vacancy); publish_notifications(session, vacancy); session.commit()
        assert session.scalar(select(RecruitmentNotification).where(RecruitmentNotification.user_id == student.id)).vacancy_id == vacancy.id
        assert len(session.scalars(select(RecruitmentNotification)).all()) == 1
    assert safe_cell("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert safe_cell("ABC123") == "ABC123"


def test_vacancy_open_window_and_application_uniqueness():
    point = datetime.now(timezone.utc)
    vacancy = DemonstratorVacancy(available_positions=1, state="OPEN", opens_at=point - timedelta(minutes=1), closes_at=point + timedelta(minutes=1), course_name="DMI", semester="Spring", description="d", responsibilities="r", created_by_id=1)
    assert application_open(vacancy)
    vacancy.available_positions = 0
    assert not application_open(vacancy)
    assert DemonstratorApplication.__table__.constraints
