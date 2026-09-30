"""Opaque session tokens, Argon2id hashing, and explicit role dependencies."""
from collections import defaultdict, deque
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from secrets import token_urlsafe,compare_digest
from threading import Lock
from time import monotonic
from typing import Annotated
from fastapi import Depends,HTTPException,Request,Response,Header
from pwdlib import PasswordHash
from sqlalchemy import select,delete
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_session
from app.auth_models import User,AuthSession

passwords=PasswordHash.recommended()
# Dummy work avoids the fast unknown-account branch. No secret or password is logged.
DUMMY_HASH=passwords.hash(token_urlsafe(32))
COOKIE='dmi_session'


def digest(token:str)->str:
    return sha256(token.encode()).hexdigest()


def issue_session(session:Session,user:User,response:Response)->str:
    token=token_urlsafe(32)
    csrf=token_urlsafe(32)
    settings=get_settings()
    now=datetime.now(timezone.utc)
    session.execute(delete(AuthSession).where(AuthSession.expires_at<=now))
    session.add(AuthSession(token_hash=digest(token),user_id=user.id,csrf_token=csrf,
        expires_at=now+timedelta(hours=settings.auth_session_hours)))
    session.commit()
    response.set_cookie(COOKIE,token,httponly=True,secure=settings.auth_cookie_secure,
        samesite='lax',max_age=settings.auth_session_hours*3600,path='/')
    return csrf


def revoke_user_sessions(session:Session,user_id:int):
    session.execute(delete(AuthSession).where(AuthSession.user_id==user_id))


def get_current_user(request:Request,session:Annotated[Session,Depends(get_session)],csrf_header:Annotated[str | None,Header(alias='X-CSRF-Token',description='For mutations: copy csrf_token from /auth/login or /auth/me.')]=None)->User:
    token=request.cookies.get(COOKIE,'')
    if not token or len(token)>256:
        raise HTTPException(401,'Sign in to continue')
    auth=session.get(AuthSession,digest(token))
    if auth is None or auth.expires_at<=datetime.now(timezone.utc):
        raise HTTPException(401,'Session expired. Sign in again')
    user=session.get(User,auth.user_id)
    if user is None or not user.is_active or user.is_legacy:
        raise HTTPException(401,'Account unavailable. Sign in with an active account')
    if request.method not in {'GET','HEAD','OPTIONS'}:
        csrf=csrf_header or ''
        if not compare_digest(csrf.encode('utf-8'),auth.csrf_token.encode('utf-8')):
            raise HTTPException(403,'Invalid CSRF token')
    request.state.auth_session=auth
    return user


def require_roles(*roles):
    def dependency(user:Annotated[User,Depends(get_current_user)]):
        if user.role not in roles:
            raise HTTPException(403,'You do not have permission for this action')
        return user
    return dependency

staff_user=require_roles('DEMONSTRATOR','LECTURER','ADMIN')
manager_user=require_roles('LECTURER','ADMIN')
student_user=require_roles('STUDENT')

# Local single-process abuse guard; replace with a shared limiter at deployment.
_failures:dict[str,deque]=defaultdict(deque)
_limiter_lock=Lock()

def limit_auth(request:Request):
    key=request.client.host if request.client else 'unknown'
    now=monotonic()
    with _limiter_lock:
        for old in list(_failures):
            while _failures[old] and _failures[old][0]<now-60:
                _failures[old].popleft()
            if not _failures[old]: del _failures[old]
        if len(_failures)>=10000 and key not in _failures:
            raise HTTPException(429,'Try again later',headers={'Retry-After':'60'})
        if len(_failures[key])>=get_settings().auth_requests_per_minute:
            raise HTTPException(429,'Too many sign-in attempts. Try again later',headers={'Retry-After':'60'})
        _failures[key].append(now)
