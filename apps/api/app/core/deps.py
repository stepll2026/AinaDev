"""FastAPI 依赖：认证、权限、MCP 鉴权。"""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.db import get_db
from app.core.security import decode_token
from app.models import User

CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="未登录或登录已过期",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise CREDENTIALS_EXC
    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token, "access")
    if not payload:
        raise CREDENTIALS_EXC
    user = await db.get(User, int(payload["sub"]))
    if not user or user.deleted_at is not None or user.status != "active":
        raise CREDENTIALS_EXC
    return user


async def get_optional_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    payload = decode_token(authorization.split(" ", 1)[1].strip(), "access")
    if not payload:
        return None
    return await db.get(User, int(payload["sub"]))


async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    return user


async def require_mcp_token(authorization: str | None = Header(default=None)) -> None:
    """MCP 端点鉴权：Bearer <MCP_API_KEY>。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 MCP 访问令牌")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.mcp_api_key:
        raise HTTPException(status_code=401, detail="MCP 访问令牌无效")


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)
