"""管理：栏目 CRUD + 人类管理员 + AI 管理员。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_super_admin
from app.models import Category, CategoryAiAdmin, CategoryHumanAdmin, Post, User
from app.schemas import AiAdminIn, AiAdminOut, CategoryIn, CategoryOut, CategoryUpdate, HumanAdminOut
from app.services.audit_service import audit

router = APIRouter(prefix="/api/admin/categories", tags=["admin-categories"])


def _cat_out(c: Category) -> CategoryOut:
    return CategoryOut(
        id=c.id, slug=c.slug, name=c.name, description=c.description, icon=c.icon,
        sort_order=c.sort_order, allow_post=c.allow_post, auto_reply_enabled=c.auto_reply_enabled,
        reply_threshold=c.reply_threshold, notify_human_on_no_evidence=c.notify_human_on_no_evidence,
    )


@router.get("", response_model=list[CategoryOut])
async def admin_list_categories(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    cats = list(await db.scalars(select(Category).where(Category.deleted_at.is_(None)).order_by(Category.sort_order)))
    result = []
    for c in cats:
        out = _cat_out(c)
        out.post_count = await db.scalar(select(func.count(Post.id)).where(Post.category_id == c.id, Post.deleted_at.is_(None))) or 0
        ai = await db.scalar(select(CategoryAiAdmin).where(CategoryAiAdmin.category_id == c.id))
        out.ai_admin = ai
        result.append(out)
    return result


@router.post("", response_model=CategoryOut)
async def create_category(body: CategoryIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    exists = await db.scalar(select(Category.id).where(Category.slug == body.slug, Category.deleted_at.is_(None)))
    if exists:
        raise HTTPException(status_code=400, detail="slug 已存在")
    cat = Category(**body.model_dump())
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    await audit(db, "user", admin.id, "category_create", "category", cat.id, {"slug": cat.slug})
    return _cat_out(cat)


@router.put("/{category_id}", response_model=CategoryOut)
async def update_category(category_id: int, body: CategoryUpdate, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    cat = await db.get(Category, category_id)
    if not cat or cat.deleted_at is not None:
        raise HTTPException(status_code=404, detail="栏目不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    await db.commit()
    await audit(db, "user", admin.id, "category_update", "category", category_id, body.model_dump(exclude_unset=True))
    return _cat_out(cat)


@router.delete("/{category_id}")
async def delete_category(category_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    cat = await db.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="栏目不存在")
    from datetime import datetime, timezone

    cat.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    await audit(db, "user", admin.id, "category_delete", "category", category_id)
    return {"ok": True}


# ---------- 人类管理员 ----------
@router.get("/{category_id}/admins", response_model=list[HumanAdminOut])
async def list_human_admins(category_id: int, db: AsyncSession = Depends(get_db)):
    rows = list(
        await db.execute(
            select(User.id, User.name, User.email)
            .join(CategoryHumanAdmin, CategoryHumanAdmin.user_id == User.id)
            .where(CategoryHumanAdmin.category_id == category_id)
        )
    )
    return [HumanAdminOut(user_id=r.id, name=r.name, email=r.email) for r in rows]


@router.post("/{category_id}/admins/{user_id}")
async def add_human_admin(category_id: int, user_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    exists = await db.scalar(
        select(CategoryHumanAdmin.id).where(CategoryHumanAdmin.category_id == category_id, CategoryHumanAdmin.user_id == user_id)
    )
    if not exists:
        db.add(CategoryHumanAdmin(category_id=category_id, user_id=user_id))
        await db.commit()
        await audit(db, "user", admin.id, "admin_bind", "category", category_id, {"user_id": user_id})
    return {"ok": True}


@router.delete("/{category_id}/admins/{user_id}")
async def remove_human_admin(category_id: int, user_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    await db.execute(
        delete(CategoryHumanAdmin).where(CategoryHumanAdmin.category_id == category_id, CategoryHumanAdmin.user_id == user_id)
    )
    await db.commit()
    await audit(db, "user", admin.id, "admin_unbind", "category", category_id, {"user_id": user_id})
    return {"ok": True}


# ---------- AI 管理员 ----------
@router.get("/{category_id}/ai-admin", response_model=AiAdminOut | None)
async def get_ai_admin(category_id: int, db: AsyncSession = Depends(get_db)):
    aa = await db.scalar(select(CategoryAiAdmin).where(CategoryAiAdmin.category_id == category_id))
    return aa


@router.post("/{category_id}/ai-admin", response_model=AiAdminOut)
async def upsert_ai_admin(
    category_id: int, body: AiAdminIn,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """创建/更新栏目 AI 管理员（自动创建 agent 类型账号，不可登录）。"""
    cat = await db.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="栏目不存在")
    aa = await db.scalar(select(CategoryAiAdmin).where(CategoryAiAdmin.category_id == category_id))

    if not aa:
        # 创建 agent 账号
        agent_email = f"ai-{cat.slug}@community.local"
        agent = await db.scalar(select(User).where(User.email == agent_email))
        if not agent:
            agent = User(email=agent_email, name=body.persona_name, account_type="agent", role="member", status="active")
            db.add(agent)
            await db.flush()
        else:
            agent.name = body.persona_name
        aa = CategoryAiAdmin(category_id=category_id, user_id=agent.id, **body.model_dump())
        db.add(aa)
    else:
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(aa, k, v)
        agent = await db.get(User, aa.user_id)
        if agent:
            agent.name = body.persona_name
    await db.commit()
    await db.refresh(aa)
    await audit(db, "user", admin.id, "ai_admin_upsert", "category", category_id, {"persona": body.persona_name})
    return aa


@router.delete("/{category_id}/ai-admin")
async def delete_ai_admin(category_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    aa = await db.scalar(select(CategoryAiAdmin).where(CategoryAiAdmin.category_id == category_id))
    if aa:
        await db.delete(aa)
        await db.commit()
        await audit(db, "user", admin.id, "ai_admin_delete", "category", category_id)
    return {"ok": True}
