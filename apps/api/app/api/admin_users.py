"""管理：用户 + 邀请码。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import Invitation, User
from app.schemas import InviteCreate, InviteOut, UserAdminUpdate, UserOut
from app.services.audit_service import audit
from app.services.auth_service import create_invite

router = APIRouter(prefix="/api/admin", tags=["admin-users"])


@router.get("/users", response_model=dict)
async def list_users(
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.deleted_at.is_(None), User.account_type == "human")
    if q:
        stmt = stmt.where(or_(User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    stmt = stmt.order_by(User.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return {"total": total or 0, "items": [UserOut.model_validate(u) for u in rows]}


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, body: UserAdminUpdate, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id and body.status == "disabled":
        raise HTTPException(status_code=400, detail="不能禁用自己")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    await db.commit()
    await audit(db, "user", admin.id, "user_update", "user", user_id, body.model_dump(exclude_unset=True))
    return UserOut.model_validate(user)


@router.post("/invitations", response_model=InviteOut)
async def create_invitation(body: InviteCreate, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    inv = await create_invite(db, admin, body.email, body.note)
    await audit(db, "user", admin.id, "invite_create", "invitation", inv.id)
    return InviteOut.model_validate(inv)


@router.get("/invitations", response_model=list[InviteOut])
async def list_invitations(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(Invitation).order_by(Invitation.created_at.desc()).limit(200)))
    return [InviteOut.model_validate(i) for i in rows]


@router.delete("/invitations/{invite_id}")
async def revoke_invitation(invite_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    inv = await db.get(Invitation, invite_id)
    if not inv:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    inv.status = "revoked"
    await db.commit()
    return {"ok": True}
