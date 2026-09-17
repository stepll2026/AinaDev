"""用户与邀请码模型。"""
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import TEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

AccountType = Enum("human", "agent", "system", name="account_type")
RoleType = Enum("super_admin", "member", name="role_type")
UserStatus = Enum("active", "invited", "disabled", name="user_status")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # account_type: human 普通用户 / agent 栏目 AI 管理员 / system 运维 Agent 与官方公告账号
    account_type: Mapped[str] = mapped_column(AccountType, default="human", server_default="human")
    role: Mapped[str] = mapped_column(RoleType, default="member", server_default="member")
    status: Mapped[str] = mapped_column(UserStatus, default="active", server_default="active")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # agent/system 账号为空=不可登录
    org_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Invitation(Base):
    """注册邀请码。"""

    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 绑定邮箱则只能该邮箱使用
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Enum("valid", "used", "revoked", name="invite_status"), default="valid", server_default="valid")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
