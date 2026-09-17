"""个人中心 + 通知 API。"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import Notification, Post, Reply, Subscription, User
from app.schemas import PostListOut, PostOut, ReplyOut

router = APIRouter(prefix="/api/me", tags=["me"])


async def _post_out(db: AsyncSession, p: Post) -> PostOut:
    from app.api.posts import _post_to_out

    return await _post_to_out(db, p, None)


async def _reply_out(db: AsyncSession, r: Reply) -> ReplyOut:
    from app.api.posts import _reply_to_out

    return await _reply_to_out(db, r, None)


@router.get("/posts", response_model=PostListOut)
async def my_posts(
    page: int = 1, page_size: int = 20,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(Post).where(Post.author_id == user.id, Post.deleted_at.is_(None)).order_by(Post.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return PostListOut(total=total or 0, items=[await _post_out(db, p) for p in rows])


@router.get("/replies", response_model=list[ReplyOut])
async def my_replies(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = list(
        await db.scalars(select(Reply).where(Reply.author_id == user.id, Reply.deleted_at.is_(None)).order_by(Reply.created_at.desc()).limit(100))
    )
    return [await _reply_out(db, r) for r in rows]


@router.get("/favorites")
async def my_favorites(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """收藏 = 订阅的栏目新帖（MVP 用 AuditLog 记录帖子点赞为收藏近似）。
    简化实现：返回我订阅栏目下的最新帖。"""
    from app.models import AuditLog, Category

    liked_ids = select(AuditLog.target_id).where(
        AuditLog.actor_type == "user", AuditLog.actor_id == user.id, AuditLog.action == "like_post"
    )
    rows = list(await db.scalars(select(Post).where(Post.id.in_(liked_ids), Post.deleted_at.is_(None)).order_by(Post.created_at.desc()).limit(50)))
    return [await _post_out(db, p) for p in rows]


@router.get("/subscriptions")
async def my_subscriptions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    subs = list(await db.scalars(select(Subscription).where(Subscription.user_id == user.id)))
    return [{"category_id": s.category_id, "tag": s.tag, "created_at": s.created_at} for s in subs]


@router.get("/notifications")
async def my_notifications(
    unread_only: bool = False, page: int = 1, page_size: int = 20,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    unread = await db.scalar(select(func.count()).where(Notification.user_id == user.id, Notification.is_read.is_(False)))
    return {
        "total": total or 0,
        "unread": unread or 0,
        "items": [
            {"id": n.id, "type": n.type, "title": n.title, "body": n.body, "link_url": n.link_url, "is_read": n.is_read, "created_at": n.created_at}
            for n in rows
        ],
    }


@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    n = await db.get(Notification, notification_id)
    if n and n.user_id == user.id:
        n.is_read = True
        await db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
async def read_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import update

    await db.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
    await db.commit()
    return {"ok": True}
