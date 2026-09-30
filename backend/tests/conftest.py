from uuid import uuid4
import pytest
from fastapi import Response
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.auth import COOKIE, issue_session, passwords, _failures
from app.auth_models import User
from app.database import get_engine

# Test-only credential, never used for persistent or browser accounts.
TEST_PASSWORD = 'test-only-password-42!'

@pytest.fixture
def accounts():
    ids=[]
    _failures.clear()
    def create(role='STUDENT',active=True):
        with Session(get_engine()) as session:
            user=User(email=f'test-{uuid4().hex}@example.com',password_hash=passwords.hash(TEST_PASSWORD),role=role,is_active=active)
            session.add(user); session.commit()
            ids.append(user.id)
            response=Response()
            csrf=issue_session(session,user,response)
            cookie=response.headers['set-cookie'].split(';')[0]
            return {'id':user.id,'email':user.email,'role':role}, {'Cookie':cookie,'X-CSRF-Token':csrf}
    yield create
    with Session(get_engine()) as session:
        session.execute(delete(User).where(User.id.in_(ids)))
        session.commit()
    _failures.clear()
