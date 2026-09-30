from datetime import datetime
from typing import Literal
from pydantic import EmailStr, Field, SecretStr, StrictBool, field_validator
from app.schemas import Schema
from app.demo_accounts import DEMO_EMAILS
Role=Literal['STUDENT','DEMONSTRATOR','LECTURER','ADMIN']

class Credentials(Schema):
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=12,max_length=128)
    @field_validator('email',mode='before')
    @classmethod
    def normalize_email(cls,value):
        return value.strip().lower() if isinstance(value,str) else value

class LoginCredentials(Credentials):
    @field_validator('email', mode='wrap')
    @classmethod
    def allow_reserved_demo_identifier(cls, value, handler):
        # Registration retains EmailStr validation; login still verifies the hash.
        normalized = value.strip().lower() if isinstance(value, str) else value
        if isinstance(normalized, str) and normalized in DEMO_EMAILS:
            return normalized
        return handler(value)

class UserRead(Schema):
    id:int
    email:str
    role:Role
    is_active:bool
    created_at:datetime

class AuthRead(Schema):
    user:UserRead
    csrf_token:str

class RoleChange(Schema):
    role:Literal['STUDENT','DEMONSTRATOR','LECTURER']

class StatusChange(Schema):
    is_active:StrictBool
