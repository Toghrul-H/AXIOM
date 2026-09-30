"""Accounts and revocable opaque browser sessions."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class User(Base):
    __tablename__='users'
    __table_args__=(CheckConstraint("role IN ('STUDENT','DEMONSTRATOR','LECTURER','ADMIN')",name='ck_users_role'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    email: Mapped[str]=mapped_column(String(254),unique=True)
    password_hash: Mapped[str | None]=mapped_column(String(512))
    role: Mapped[str]=mapped_column(String(20),default='STUDENT',server_default='STUDENT')
    is_active: Mapped[bool]=mapped_column(Boolean,default=True,server_default='true')
    is_legacy: Mapped[bool]=mapped_column(Boolean,default=False,server_default='false')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())

class AuthSession(Base):
    __tablename__='auth_sessions'
    token_hash: Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    csrf_token: Mapped[str]=mapped_column(String(64))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
