"""⑦ 异步后处理：自动打标签、重复帖检测、推送订阅者通知。"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import PipelineState
from app.models import AgentRun, Post, Subscription, User
from app.services.llm import chat_with_json
from app.services.model_service import get_default_llm_config

logger = logging.getLogger(__name__)


async def auto_tag(db: AsyncSession, post: Post) -> None:
    """LLM 提取 1-3 个标签。"""
    try:
        cfg = await get_default_llm_config(db)
        raw = await chat_with_json(
            cfg,
            "你是帖子标签生成器。输出 JSON：{\"tags\": [\"标签1\",\"标签2\"]}，1-3 个，每个不超过 8 字。",
            f"标题：{post.title}\n内容：{post.body_md[:1500]}",
            max_tokens=200,
        )
        import json

        tags = json.loads(raw).get("tags", [])[:3]
        tags = [t for t in tags if t]
        if tags:
            post.tags = list(dict.fromkeys((post.tags or []) + tags))[:5]
    except Exception as e:
        logger.warning("auto_tag failed: %s", e)


async def dedup_check(db: AsyncSession, post: Post) -> None:
    """近似重复帖检测：同栏目标题高相似（>0.9）→ 以 AI persona 评论提示。"""
    try:
        # 帖子级重复用标题近似，不检索知识库（避免把知识库文档误判为重复帖）
        import difflib

        from app.models import CategoryAiAdmin, Reply

        posts = list(
            await db.scalars(
                select(Post).where(
                    Post.category_id == post.category_id,
                    Post.id != post.id,
                    Post.status == "published",
                    Post.deleted_at.is_(None),
                ).order_by(Post.id.desc()).limit(50)
            )
        )
        similar = None
        for p in posts:
            ratio = difflib.SequenceMatcher(None, post.title, p.title).ratio()
            if ratio >= 0.9:
                similar = p
                break
        if similar:
            aa = await db.scalar(
                select(CategoryAiAdmin).where(CategoryAiAdmin.category_id == post.category_id, CategoryAiAdmin.active.is_(True))
            )
            author_id = aa.user_id if aa else None
            if not author_id:
                official = await db.scalar(select(User).where(User.email == "official@community.local"))
                author_id = official.id if official else 0
            db.add(
                Reply(
                    post_id=post.id, author_id=author_id, author_type="ai_admin",
                    ai_admin_id=aa.id if aa else None,
                    body_md=f"🔁 提示：本帖可能与已有内容重复，请确认是否重复发布。",
                    status="published",
                )
            )
    except Exception as e:
        logger.warning("dedup_check failed: %s", e)


async def notify_subscribers(db: AsyncSession, post: Post) -> None:
    """推送订阅者（关注该栏目/标签的用户）新帖通知。"""
    try:
        subs = list(
            await db.scalars(
                select(Subscription.user_id).where(
                    Subscription.category_id == post.category_id,
                    Subscription.user_id != post.author_id,
                )
            )
        )
        if subs:
            from app.services.notify_service import notify_many

            await notify_many(
                db, subs, "new_post", f"新帖：{post.title}",
                f"你关注的栏目有新帖", f"/post/{post.id}",
            )
    except Exception as e:
        logger.warning("notify_subscribers failed: %s", e)


async def async_postprocess(db: AsyncSession, state: PipelineState) -> None:
    """流水线完成后异步执行（打标签 / 重复帖检测 / 通知）。"""
    try:
        post = await db.get(Post, state.get("post_id"))
        if not post or post.status != "published":
            return
        await auto_tag(db, post)
        await dedup_check(db, post)
        await notify_subscribers(db, post)
        await db.commit()
    except Exception as e:
        logger.exception("async_postprocess failed: %s", e)
