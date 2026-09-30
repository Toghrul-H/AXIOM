"""Interactive, server-local bootstrap of the first administrator."""
from getpass import getpass
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.auth import passwords
from app.auth_models import User
from app.auth_schemas import Credentials
from app.database import get_engine


def bootstrap_admin(session: Session, credentials: Credentials) -> int:
    # Serialize concurrent bootstrap commands without a public bootstrap route.
    session.execute(text('SELECT pg_advisory_xact_lock(184271905)'))
    if session.scalar(select(User.id).where(User.role == 'ADMIN')) is not None:
        raise ValueError('An administrator already exists; bootstrap is disabled.')
    if session.scalar(select(User.id).where(User.email == str(credentials.email))) is not None:
        raise ValueError('This email is already registered. Choose a separate administrator email.')
    user=User(email=str(credentials.email),password_hash=passwords.hash(credentials.password.get_secret_value()),role='ADMIN')
    session.add(user)
    session.commit()
    return user.id


def main():
    email=input('Administrator email: ').strip()
    password=getpass('Password (12–128 characters): ')
    confirmation=getpass('Confirm password: ')
    if password != confirmation:
        raise SystemExit('Passwords do not match. Nothing was created.')
    try:
        credentials=Credentials(email=email,password=password)
    except ValidationError:
        raise SystemExit('Use a valid email and a password of 12–128 characters.') from None
    try:
        with Session(get_engine()) as session:
            bootstrap_admin(session,credentials)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print('Administrator created. Sign in through /login. No credentials were saved to a file.')


if __name__ == '__main__':
    main()
