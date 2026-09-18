"""发帖异步 AI 审核任务：审核通过才发布并触发 AI 回帖，不通过转 rejected。"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, User
from app.services.notify_service import notify

logger = logging.getLogger(__name__)


async def review_post(db: AsyncSession, post_id: int) -> str:
    """发帖审核：pending_review →（AI 通过）published + 触发 AI 回帖 /（不通过）rejected。

    审核不通过或 AI 异常时保守转 rejected，并通知栏目人类管理员处理。
    """
    post = await db.get(Post, post_id)
    if not post or post.status != "pending_review":
        return "skipped"

    from app.services.compliance_service import compliance_check

    trace_id = uuid.uuid4().hex[:16]
    try:
        result = await compliance_check(db, f"标题：{post.title}\n正文：{post.body_md[:4000]}", post.id, trace_id)
        passed = bool(result.get("pass"))
        reason = str(result.get("reason", ""))[:300]
    except Exception as exc:
        logger.exception("review_post failed: %s", exc)
        passed = False
        reason = f"AI 审核异常：{type(exc).__name__}"

    if passed:
        post.status = "published"
        post.human_needed = False
        await db.commit()
        # 审核通过后才触发 AI 回帖流水线（两次 AI 调用分开）
        from app.tasks.worker import enqueue

        try:
            await enqueue("run_pipeline_task", post.id, "post")
        except Exception:
            from app.agent.runner import trigger_pipeline

            await trigger_pipeline(db, post.id, "post")
        return "approved"

    post.status = "rejected"
    post.human_needed = True
    await db.commit()
    # 通知栏目人类管理员处理
    from app.models import CategoryHumanAdmin

    admins = list(
        await db.scalars(
            select(CategoryHumanAdmin.user_id).where(CategoryHumanAdmin.category_id == post.category_id)
        )
    )
    for uid in admins:
        await notify(
            db, uid, "review",
            f"有帖子未通过 AI 审核，待处理：{post.title[:50]}",
            reason, f"/admin?tab=reviews",
        )
    return "rejected"
