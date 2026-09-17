"""认证 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.security import decode_token, hash_password, verify_password
from app.models import User
from app.schemas import ChangePasswordIn, LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from app.services.auth_service import AuthError, issue_tokens, login, register

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
async def register_user(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    try:
        user = await register(db, body.email, body.name, body.password, body.invite_code)
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    tokens = issue_tokens(user)
    return {**tokens, "user": UserOut.model_validate(user)}


@router.post("/login", response_model=TokenOut)
async def login_user(body: LoginIn, db: AsyncSession = Depends(get_db)):
    try:
        user = await login(db, body.email, body.password)
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    tokens = issue_tokens(user)
    return {**tokens, "user": UserOut.model_validate(user)}


@router.post("/refresh", response_model=TokenOut)
async def refresh_token(body: RefreshIn, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token, "refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="刷新令牌无效")
    user = await db.get(User, int(payload["sub"]))
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="账号不可用")
    tokens = issue_tokens(user)
    return {**tokens, "user": UserOut.model_validate(user)}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not user.password_hash or not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}
