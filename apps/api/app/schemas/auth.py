"""Pydantic schemas：认证与用户。"""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------- 认证 ----------
class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    invite_code: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RefreshIn(BaseModel):
    refresh_token: str


# ---------- 用户 ----------
class UserOut(BaseModel):
    id: int
    email: str
    name: str
    avatar_url: str | None
    account_type: str
    role: str
    status: str
    org_id: str | None
    department: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserAdminUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    status: str | None = None
    department: str | None = None
    org_id: str | None = None


# ---------- 邀请码 ----------
class InviteCreate(BaseModel):
    email: str | None = None
    note: str | None = None


class InviteOut(BaseModel):
    id: int
    code: str
    email: str | None
    used_by: int | None
    used_at: datetime | None
    expires_at: datetime
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)
