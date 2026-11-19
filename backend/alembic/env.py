from alembic import context

from app.config import get_settings
from app.database import Base, get_engine
from app.models import Question  # Register models in migration metadata.
from app.quiz_models import Quiz
from app.auth_models import User, AuthSession, PasswordResetToken
from app.assessment_models import AssessmentConfiguration
from app.recruitment_models import DemonstratorVacancy
from app.exam_models import Exam
from app.practice_sheet_models import PracticeSheet
from app.study_partner_models import StudyPartnerProfile
from app.course_models import CourseChapter
from app.notification_models import Notification

target_metadata = Base.metadata


def _version_table_schema() -> str | None:
    """Allow isolated integration schemas to own their Alembic version table."""
    return context.config.attributes.get("version_table_schema") or get_settings().database_schema or None


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=_version_table_schema(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        context.configure(
            connection=supplied_connection,
            target_metadata=target_metadata,
            version_table_schema=_version_table_schema(),
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    with get_engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=_version_table_schema(),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()



