"""Explicit local-development fixtures. Never invoke in production or at startup."""

import argparse
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth import passwords, revoke_user_sessions
from app.auth_models import User
from app.config import Settings, get_settings
from app.database import get_engine

ACCOUNTS = (
    ("student1@axiom.local", "STUDENT"),
    ("demonstrator1@axiom.local", "DEMONSTRATOR"),
    ("lecturer1@axiom.local", "LECTURER"),
    ("admin1@axiom.local", "ADMIN"),
)


class DemoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Settings.model_config['env_file'], env_prefix='DEMO_', extra='ignore',
    )
    seed_enabled: bool = False
    student_password: SecretStr = SecretStr('')
    demonstrator_password: SecretStr = SecretStr('')
    lecturer_password: SecretStr = SecretStr('')
    admin_password: SecretStr = SecretStr('')


def configured_accounts():
    config = DemoSettings()
    settings = get_settings()
    if not config.seed_enabled:
        raise ValueError('Set DEMO_SEED_ENABLED=true locally to enable manual seeding.')
    if settings.database_host.lower() not in {'localhost', '127.0.0.1', '::1'} or settings.auth_cookie_secure:
        raise ValueError('Demo fixtures require a local development database and cookie configuration.')
    result = []
    for email, role in ACCOUNTS:
        password = getattr(config, role.lower() + '_password').get_secret_value()
        if not 12 <= len(password) <= 128:
            raise ValueError(f'Set DEMO_{role}_PASSWORD locally (12–128 characters).')
        result.append((email, password, role))
    return result


def ensure_demo_users(session: Session) -> None:
    accounts = configured_accounts()
    session.execute(text("SELECT pg_advisory_xact_lock(184271905)"))
    for email, password, role in accounts:
        user = session.scalar(select(User).where(User.email == email).with_for_update())
        if user is None:
            session.add(User(email=email, password_hash=passwords.hash(password),
                             role=role, is_active=True))
            continue
        if user.is_legacy:
            raise ValueError("Refusing to modify a legacy migration account.")
        password_matches = bool(user.password_hash) and passwords.verify(password, user.password_hash)
        if not password_matches or user.role != role or not user.is_active:
            revoke_user_sessions(session, user.id)
            if not password_matches:
                user.password_hash = passwords.hash(password)
            user.role = role
            user.is_active = True
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-development', action='store_true', required=True,
                        help='Confirm this is a local development database, never production.')
    parser.parse_args()
    settings = get_settings()
    if settings.database_host.lower() not in {'localhost', '127.0.0.1', '::1'} or settings.auth_cookie_secure:
        raise SystemExit('Demo fixtures require a local development database and cookie configuration.')
    try:
        configured_accounts()  # Validate before opening a database connection.
        with Session(get_engine()) as session:
            ensure_demo_users(session)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print('Four local development accounts are ready. Use Sign In.')


if __name__ == '__main__':
    main()
