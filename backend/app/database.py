from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    connect_args = {"connect_timeout": 5}
    if settings.database_schema:
        # The value is constrained in Settings. Keeping public second allows
        # PostgreSQL built-ins while ensuring application tables resolve in the
        # disposable schema first.
        connect_args["options"] = f"-c search_path={settings.database_schema},public"
    return create_engine(
        settings.database_url(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args=connect_args,
    )


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
