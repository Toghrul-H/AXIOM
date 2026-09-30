from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,Request,Response,Query,Path
from sqlalchemy import select,delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_session
from app.auth import COOKIE,passwords,DUMMY_HASH,digest,issue_session,get_current_user,manager_user,revoke_user_sessions,limit_auth
from app.auth_models import User,AuthSession
from app.auth_schemas import Credentials,LoginCredentials,UserRead,AuthRead,RoleChange,StatusChange

router=APIRouter(tags=['Authentication and users'])
DB=Annotated[Session,Depends(get_session)]
Current=Annotated[User,Depends(get_current_user)]
Manager=Annotated[User,Depends(manager_user)]
Id=Annotated[int,Path(gt=0)]

@router.post('/auth/register',response_model=UserRead,status_code=201,dependencies=[Depends(limit_auth)])
def register(payload:Credentials,session:DB):
    user=User(email=str(payload.email).lower(),password_hash=passwords.hash(payload.password.get_secret_value()),role='STUDENT')
    session.add(user)
    try: session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409,'An account with this email already exists') from None
    return user

@router.post('/auth/login',response_model=AuthRead,dependencies=[Depends(limit_auth)])
def login(payload:LoginCredentials,session:DB,response:Response,request:Request):
    user=session.scalar(select(User).where(User.email==str(payload.email).lower()).with_for_update())
    candidate=user.password_hash if user and user.password_hash else DUMMY_HASH
    valid=passwords.verify(payload.password.get_secret_value(),candidate)
    if not valid or user is None or not user.is_active or user.is_legacy:
        raise HTTPException(401,'Invalid email or password')
    old=request.cookies.get(COOKIE)
    if old: session.execute(delete(AuthSession).where(AuthSession.token_hash==digest(old)))
    return {'user':user,'csrf_token':issue_session(session,user,response)}

@router.get('/auth/me',response_model=AuthRead)
def me(user:Current,request:Request):
    return {'user':user,'csrf_token':request.state.auth_session.csrf_token}

@router.post('/auth/logout',status_code=204)
def logout(user:Current,session:DB,request:Request,response:Response):
    session.delete(request.state.auth_session)
    session.commit()
    response.delete_cookie(COOKIE,path='/')

@router.get('/users',response_model=list[UserRead])
def list_users(actor:Manager,session:DB,q:Annotated[str,Query(max_length=254)]='',offset:Annotated[int,Query(ge=0)]=0,limit:Annotated[int,Query(ge=1,le=100)]=20):
    roles=['STUDENT','DEMONSTRATOR'] if actor.role=='LECTURER' else ['STUDENT','DEMONSTRATOR','LECTURER']
    return list(session.scalars(select(User).where(User.is_legacy.is_(False),User.role.in_(roles),User.email.icontains(q.strip(),autoescape=True)).order_by(User.id).offset(offset).limit(limit)))


def managed_target(session:Session,actor:User,target_id:int)->User:
    # Lock both actor and target before checking the live hierarchy.
    session.refresh(actor,with_for_update=True)
    if not actor.is_active or actor.role not in {'LECTURER','ADMIN'}:
        raise HTTPException(403,'Account management permission required')
    target=session.scalar(select(User).where(User.id==target_id).with_for_update())
    if target is None: raise HTTPException(404,'User not found')
    if target.id==actor.id or target.is_legacy or target.role=='ADMIN':
        raise HTTPException(403,'This account cannot be managed here')
    if actor.role=='LECTURER' and target.role not in {'STUDENT','DEMONSTRATOR'}:
        raise HTTPException(403,'Lecturers may manage demonstrators only')
    return target

@router.post('/users/{user_id}/role',response_model=UserRead)
def change_role(user_id:Id,payload:RoleChange,actor:Manager,session:DB):
    target=managed_target(session,actor,user_id)
    allowed={('STUDENT','DEMONSTRATOR'),('DEMONSTRATOR','STUDENT')}
    if actor.role=='ADMIN': allowed|={('STUDENT','LECTURER'),('DEMONSTRATOR','LECTURER'),('LECTURER','STUDENT'),('LECTURER','DEMONSTRATOR')}
    if (target.role,payload.role) not in allowed: raise HTTPException(403,'Role transition is not permitted')
    target.role=payload.role
    revoke_user_sessions(session,target.id)
    session.commit()
    return target

@router.post('/users/{user_id}/status',response_model=UserRead)
def change_status(user_id:Id,payload:StatusChange,actor:Manager,session:DB):
    target=managed_target(session,actor,user_id)
    permitted={'DEMONSTRATOR'} if actor.role=='LECTURER' else {'STUDENT','DEMONSTRATOR','LECTURER'}
    if target.role not in permitted: raise HTTPException(403,'This account status cannot be changed by your role')
    target.is_active=payload.is_active
    revoke_user_sessions(session,target.id)
    session.commit()
    return target
