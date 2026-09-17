"""管理：AI 资讯源 CRUD + 手动抓取。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.models import AiNewsSource, User
from app.schemas import NewsSourceIn, NewsSourceOut
from app.services.audit_service import audit

router = APIRouter(prefix="/api/admin/news-sources", tags=["admin-news"])


def _out(s: AiNewsSource) -> NewsSourceOut:
    return NewsSourceOut(
        id=s.id, name=s.name, type=s.type, url=s.url, target_category_id=s.target_category_id,
        enabled=s.enabled, fetch_cron=s.fetch_cron, last_fetched_at=s.last_fetched_at, created_at=s.created_at,
    )


@router.get("", response_model=list[NewsSourceOut])
async def list_sources(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(AiNewsSource).where(AiNewsSource.deleted_at.is_(None)).order_by(AiNewsSource.id)))
    return [_out(s) for s in rows]


@router.post("", response_model=NewsSourceOut)
async def create_source(body: NewsSourceIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    src = AiNewsSource(**body.model_dump())
    db.add(src)
    await db.commit()
    await db.refresh(src)
    await audit(db, "user", admin.id, "news_source_create", "news_source", src.id, {"name": src.name})
    return _out(src)


@router.put("/{source_id}", response_model=NewsSourceOut)
async def update_source(source_id: int, body: NewsSourceIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    src = await db.get(AiNewsSource, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="资讯源不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(src, k, v)
    await db.commit()
    return _out(src)


@router.delete("/{source_id}")
async def delete_source(source_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone

    src = await db.get(AiNewsSource, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="资讯源不存在")
    src.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.post("/{source_id}/fetch")
async def fetch_now(source_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from app.services.news_service import digest_and_publish

    src = await db.get(AiNewsSource, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="资讯源不存在")
    try:
        published = await digest_and_publish(db, src)
        return {"published": published}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"抓取失败：{str(e)[:200]}")
