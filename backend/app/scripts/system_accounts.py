"""Private deployment-owner provisioning. No public route or startup hook."""
import argparse
from getpass import getpass
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.auth import revoke_user_sessions
from app.auth_models import User, EmailVerification
from app.auth_schemas import Credentials, ResendInput
from app.database import get_engine
from app.scripts.create_admin import bootstrap_admin

def create_protected_admin(session: Session, credentials: Credentials) -> int:
    # Preserve the existing first-admin-only rule and advisory lock.
    # A savepoint keeps bootstrap_admin's commit inside our caller's transaction.
    with Session(session.connection(), join_transaction_mode='create_savepoint') as nested:
        user_id = bootstrap_admin(nested, credentials)
    user = session.get(User, user_id)
    user.is_system_managed = True
    user.email_verified = True
    session.flush()
    return user_id

def protect_existing(session: Session, user_id: int, expected_email: str) -> int:
    user = session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or user.email != expected_email:
        raise ValueError('Account ID/email mismatch; nothing changed.')
    if user.is_legacy or not user.is_active or not user.password_hash:
        raise ValueError('Refusing a legacy, inactive or passwordless account.')
    user.is_system_managed = True
    user.email_verified = True
    session.execute(delete(EmailVerification).where(EmailVerification.user_id == user.id))
    revoke_user_sessions(session, user.id)
    session.flush()
    return user.id

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('create-admin', help='Create the first Admin as protected and verified; refuses if any Admin exists.')
    protect = commands.add_parser('protect', help='Protect and verify an existing active account; preserve role/password and revoke sessions.')
    protect.add_argument('--user-id', type=int, required=True)
    args = parser.parse_args()
    try:
        email = str(ResendInput(email=input('Exact account email: ')).email)
        credentials = None
        if args.action == 'create-admin':
            password = getpass('New administrator password (12–128 characters): ')
            if password != getpass('Confirm password: '):
                raise ValueError('Passwords do not match.')
            credentials = Credentials(email=email, password=password)
        engine = get_engine()
        print(f'Target database: {engine.url.host}:{engine.url.port}/{engine.url.database}')
        print(f'{args.action}: {email}' + (f' (ID {args.user_id})' if args.action == 'protect' else ' (first ADMIN only)'))
        print('Account will be protected and email-verified. Existing role/password are preserved when protecting; sessions are revoked.')
        if input('Type PROTECT to confirm private owner authorization: ') != 'PROTECT':
            raise ValueError('Cancelled; nothing changed.')
        with Session(engine) as session, session.begin():
            if credentials is not None:
                user_id = create_protected_admin(session, credentials)
            else:
                user_id = protect_existing(session, args.user_id, email)
        print(f'Protected account #{user_id} is ready. Use Sign In.')
    except ValidationError:
        raise SystemExit('Invalid email or password length. Nothing changed.') from None
    except IntegrityError:
        raise SystemExit('Conflicting account; nothing changed.') from None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

if __name__ == '__main__':
    main()
