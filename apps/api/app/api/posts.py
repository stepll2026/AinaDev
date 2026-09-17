"""帖子 API：发帖、Feed、详情、搜索、互动。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, get_optional_user
from app.models import Category, Post, Reply, Subscription, User
from app.schemas import PostIn, PostListOut, PostOut, ReplyIn, ReplyOut, SearchQuery
from app.services.audit_service import audit
from app.services.notify_service import notify

router = APIRouter(prefix="/api", tags=["posts"])

FEED_SORTS = {"latest", "hot", "unanswered", "following"}


async def _post_to_out(db: AsyncSession, p: Post, user: User | None) -> PostOut:
    author = await db.get(User, p.author_id)
    cat = await db.get(Category, p.category_id)
    is_liked = False
    is_sub = False
    if user:
        from app.models import AuditLog

        is_liked = await db.scalar(
            select(AuditLog.id).where(
                AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
                AuditLog.action == "like_post", AuditLog.target_id == p.id,
            )
        ) is not None
        is_sub = await db.scalar(
            select(Subscription.id).where(
                Subscription.user_id == user.id, Subscription.category_id == p.category_id, Subscription.tag.is_(None)
            )
        ) is not None
    author_type = "ai_agent" if author and author.account_type in ("agent", "system") else "human"
    return PostOut(
        id=p.id, category_id=p.category_id, category_name=cat.name if cat else None,
        author_id=p.author_id, author_name=author.name if author else None,
        author_avatar=author.avatar_url if author else None, author_type=author_type,
        title=p.title, body_md=p.body_md, post_type=p.post_type, status=p.status,
        pinned=p.pinned, featured=p.featured, locked=p.locked, is_solved=p.is_solved,
        tags=p.tags, attachments=p.attachments or [], view_count=p.view_count, like_count=p.like_count, reply_count=p.reply_count,
        ai_handled=p.ai_handled, human_needed=p.human_needed,
        created_at=p.created_at, updated_at=p.updated_at,
        is_liked=is_liked, is_subscribed=is_sub,
    )


async def _reply_to_out(db: AsyncSession, r: Reply, user: User | None) -> ReplyOut:
    author = await db.get(User, r.author_id)
    is_liked = False
    if user:
        from app.models import AuditLog

        is_liked = await db.scalar(
            select(AuditLog.id).where(
                AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
                AuditLog.action == "like_reply", AuditLog.target_id == r.id,
            )
        ) is not None
    return ReplyOut(
        id=r.id, post_id=r.post_id, parent_reply_id=r.parent_reply_id,
        author_id=r.author_id, author_name=author.name if author else None,
        author_avatar=author.avatar_url if author else None, author_type=r.author_type,
        body_md=r.body_md, status=r.status, citations=r.citations,
        attachments=r.attachments or [],
        like_count=r.like_count, created_at=r.created_at, is_liked=is_liked,
    )


@router.post("/posts", response_model=PostOut)
async def create_post(body: PostIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    cat = await db.get(Category, body.category_id)
    if not cat or cat.deleted_at is not None:
        raise HTTPException(status_code=404, detail="栏目不存在")
    if not cat.allow_post:
        raise HTTPException(status_code=403, detail="该栏目不允许发帖")

    post = Post(
        category_id=body.category_id, author_id=user.id,
        title=body.title.strip(), body_md=body.body_md,
        post_type=body.post_type, status="published", tags=body.tags[:5],
        attachments=[a.model_dump() for a in (body.attachments or [])][:20],
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    # 触发 AI 原生流水线（worker 异步执行）
    from app.tasks.worker import enqueue

    try:
        await enqueue("run_pipeline_task", post.id, "post")
    except Exception:
        # Redis 不可用时同步执行（降级不阻塞发帖）
        from app.agent.runner import trigger_pipeline

        await trigger_pipeline(db, post.id, "post")
    return await _post_to_out(db, post, user)


@router.get("/posts", response_model=PostListOut)
async def list_posts(
    sort: str = Query("latest", pattern="^(latest|hot|unanswered|following)$"),
    category_id: int | None = None,
    tag: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Post).where(Post.status == "published", Post.deleted_at.is_(None))
    if category_id:
        stmt = stmt.where(Post.category_id == category_id)
    if tag:
        stmt = stmt.where(Post.tags.any(tag))

    if sort == "hot":
        stmt = stmt.order_by(Post.reply_count.desc(), Post.view_count.desc(), Post.created_at.desc())
    elif sort == "unanswered":
        stmt = stmt.where(Post.reply_count == 0).order_by(Post.created_at.desc())
    elif sort == "following":
        if not user:
            raise HTTPException(status_code=401, detail="请先登录")
        sub_cats = select(Subscription.category_id).where(Subscription.user_id == user.id, Subscription.tag.is_(None))
        stmt = stmt.where(Post.category_id.in_(sub_cats)).order_by(Post.created_at.desc())
    else:
        stmt = stmt.order_by(Post.pinned.desc(), Post.created_at.desc())

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    items = [await _post_to_out(db, p, user) for p in rows]
    return PostListOut(total=total or 0, items=items)


@router.get("/posts/{post_id}", response_model=PostOut)
async def get_post(
    post_id: int,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post or post.deleted_at is not None or post.status not in ("published", "hidden", "pending_review"):
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.status in ("hidden", "pending_review") and (not user or user.id != post.author_id):
        from app.models import CategoryHumanAdmin

        is_admin = await db.scalar(
            select(CategoryHumanAdmin.id).where(
                CategoryHumanAdmin.category_id == post.category_id, CategoryHumanAdmin.user_id == user.id
            )
        ) if user else None
        is_super = user.role == "super_admin" if user else False
        if not is_admin and not is_super:
            raise HTTPException(status_code=404, detail="帖子不存在")
    post.view_count += 1
    await db.commit()
    await db.refresh(post)  # commit 后重新加载所有列，避免懒加载触发 MissingGreenlet
    return await _post_to_out(db, post, user)


@router.get("/posts/{post_id}/replies", response_model=list[ReplyOut])
async def list_replies(
    post_id: int,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    rows = list(
        await db.scalars(
            select(Reply).where(
                Reply.post_id == post_id, Reply.deleted_at.is_(None),
                or_(Reply.status == "published", Reply.status == "pending_review"),
            ).order_by(Reply.created_at.asc())
        )
    )
    return [await _reply_to_out(db, r, user) for r in rows]


@router.post("/posts/{post_id}/replies", response_model=ReplyOut)
async def create_reply(
    post_id: int, body: ReplyIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(Post, post_id)
    if not post or post.status != "published" or post.deleted_at is not None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.locked:
        raise HTTPException(status_code=403, detail="帖子已锁定，禁止回复")
    if body.parent_reply_id:
        parent = await db.get(Reply, body.parent_reply_id)
        if not parent or parent.post_id != post_id:
            raise HTTPException(status_code=400, detail="父回复不存在")

    reply = Reply(
        post_id=post_id, parent_reply_id=body.parent_reply_id,
        author_id=user.id, author_type="user", body_md=body.body_md,
        status="published",
        attachments=[a.model_dump() for a in (body.attachments or [])][:20],
    )
    db.add(reply)
    post.reply_count += 1
    await db.commit()
    await db.refresh(reply)

    # 回帖触发合规审查（worker 异步）
    from app.tasks.worker import enqueue

    try:
        await enqueue("run_pipeline_task", post_id, "reply")
    except Exception:
        from app.agent.runner import trigger_pipeline

        await trigger_pipeline(db, post_id, "reply")

    # 通知楼主
    if post.author_id != user.id:
        await notify(db, post.author_id, "reply", f"{user.name} 回复了你的帖子", reply.body_md[:200], f"/post/{post_id}")
    return await _reply_to_out(db, reply, user)


@router.post("/posts/{post_id}/like")
async def like_post(post_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import AuditLog

    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    existing = await db.scalar(
        select(AuditLog.id).where(
            AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
            AuditLog.action == "like_post", AuditLog.target_id == post_id,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="已点赞")
    db.add(AuditLog(actor_type="user", actor_id=user.id, action="like_post", target_type="post", target_id=post_id))
    post.like_count += 1
    await db.commit()
    return {"like_count": post.like_count}


@router.post("/posts/{post_id}/unlike")
async def unlike_post(post_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import AuditLog

    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    log = await db.scalar(
        select(AuditLog).where(
            AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
            AuditLog.action == "like_post", AuditLog.target_id == post_id,
        )
    )
    if log:
        await db.delete(log)
        post.like_count = max(0, post.like_count - 1)
        await db.commit()
    return {"like_count": post.like_count}


@router.post("/replies/{reply_id}/like")
async def like_reply(reply_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import AuditLog

    reply = await db.get(Reply, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="回复不存在")
    existing = await db.scalar(
        select(AuditLog.id).where(
            AuditLog.actor_type == "user", AuditLog.actor_id == user.id,
            AuditLog.action == "like_reply", AuditLog.target_id == reply_id,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="已点赞")
    db.add(AuditLog(actor_type="user", actor_id=user.id, action="like_reply", target_type="reply", target_id=reply_id))
    reply.like_count += 1
    await db.commit()
    return {"like_count": reply.like_count}


@router.post("/posts/{post_id}/subscribe")
async def subscribe_category(post_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    existing = await db.scalar(
        select(Subscription.id).where(
            Subscription.user_id == user.id, Subscription.category_id == post.category_id, Subscription.tag.is_(None)
        )
    )
    if not existing:
        db.add(Subscription(user_id=user.id, category_id=post.category_id))
        await db.commit()
    return {"ok": True}


@router.post("/posts/{post_id}/unsubscribe")
async def unsubscribe_category(post_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id, Subscription.category_id == post.category_id, Subscription.tag.is_(None)
        )
    )
    if sub:
        await db.delete(sub)
        await db.commit()
    return {"ok": True}


@router.post("/posts/{post_id}/report")
async def report_post(post_id: int, reason: str = Query(min_length=1), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import Report

    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    db.add(Report(reporter_id=user.id, target_type="post", target_id=post_id, reason=reason))
    await db.commit()
    return {"ok": True}


@router.post("/replies/{reply_id}/report")
async def report_reply(reply_id: int, reason: str = Query(min_length=1), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import Report

    reply = await db.get(Reply, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="回复不存在")
    db.add(Report(reporter_id=user.id, target_type="reply", target_id=reply_id, reason=reason))
    await db.commit()
    return {"ok": True}


@router.post("/posts/{post_id}/solved")
async def mark_solved(post_id: int, solved: bool = Query(True), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if post.author_id != user.id:
        raise HTTPException(status_code=403, detail="只有楼主可以标记已解决")
    post.is_solved = solved
    await db.commit()
    return {"is_solved": post.is_solved}


@router.get("/search")
async def search(
    q: str = Query(min_length=1),
    category_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """搜索：zhparser 中文分词 FTS（生产）或 ILIKE 兜底（Windows 开发）。"""
    from sqlalchemy import text as sa_text

    from app.config import settings

    stmt = select(Post).where(Post.status == "published", Post.deleted_at.is_(None))
    if settings.fulltext_mode == "zhparser":
        stmt = stmt.where(
            sa_text("posts.title @@ plainto_tsquery('zh', :q) OR posts.body_md @@ plainto_tsquery('zh', :q)").bindparams(q=q)
        )
    else:
        stmt = stmt.where(or_(Post.title.ilike(f"%{q}%"), Post.body_md.ilike(f"%{q}%")))
    if category_id:
        stmt = stmt.where(Post.category_id == category_id)
    stmt = stmt.order_by(Post.created_at.desc())
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = list(await db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    items = [await _post_to_out(db, p, None) for p in rows]
    return PostListOut(total=total or 0, items=items)
