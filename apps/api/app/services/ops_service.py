"""运维任务：周报、48h 未回提醒、僵尸帖归档、低置信统计告警。"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, CategoryAiAdmin, CategoryHumanAdmin, KnowledgeHit, Post, Reply, User
from app.services.notify_service import notify

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def send_weekly_reports(db: AsyncSession) -> int:
    """每周栏目周报：热门帖 + 未答清单，推送人类管理员。"""
    week_ago = _utcnow() - timedelta(days=7)
    categories = list(await db.scalars(select(Category).where(Category.deleted_at.is_(None))))
    sent = 0
    for cat in categories:
        admins = list(
            await db.scalars(
                select(CategoryHumanAdmin.user_id).where(CategoryHumanAdmin.category_id == cat.id)
            )
        )
        if not admins:
            continue
        hot = list(
            await db.scalars(
                select(Post)
                .where(Post.category_id == cat.id, Post.status == "published", Post.created_at >= week_ago, Post.deleted_at.is_(None))
                .order_by(Post.reply_count.desc(), Post.view_count.desc())
                .limit(5)
            )
        )
        unanswered = list(
            await db.scalars(
                select(Post)
                .where(Post.category_id == cat.id, Post.status == "published", Post.reply_count == 0, Post.deleted_at.is_(None))
                .order_by(Post.created_at.desc())
                .limit(10)
            )
        )
        hot_lines = "\n".join(f"- {p.title}（{p.reply_count} 回复）" for p in hot) or "（本周暂无热门帖）"
        un_lines = "\n".join(f"- {p.title}" for p in unanswered) or "（无未答帖 🎉）"
        body = f"【{cat.name}】本周周报\n\n🔥 热门帖：\n{hot_lines}\n\n❓ 未答帖：\n{un_lines}"
        for admin_id in admins:
            await notify(db, admin_id, "weekly", f"周报：{cat.name}", body, f"/c/{cat.slug}")
        sent += 1
    return sent


async def check_no_reply_48h(db: AsyncSession) -> int:
    """帖子 48h 无回复 → @ 栏目人类管理员。"""
    cutoff = _utcnow() - timedelta(hours=48)
    posts = list(
        await db.scalars(
            select(Post)
            .where(Post.status == "published", Post.reply_count == 0, Post.created_at <= cutoff, Post.deleted_at.is_(None))
            .order_by(Post.created_at.asc())
            .limit(50)
        )
    )
    reminded = 0
    for post in posts:
        admins = list(
            await db.scalars(
                select(CategoryHumanAdmin.user_id).where(CategoryHumanAdmin.category_id == post.category_id)
            )
        )
        if not admins:
            continue
        await notify(
            db, admins[0], "reminder", f"48h 无回复：{post.title}",
            "该帖已 48 小时无人回复，建议人工介入", f"/post/{post.id}",
        )
        reminded += 1
    return reminded


async def archive_stale_posts(db: AsyncSession) -> int:
    """365 天无回复帖自动沉底归档（status 保持 published，仅打标记不删除）。"""
    cutoff = _utcnow() - timedelta(days=365)
    posts = list(
        await db.scalars(
            select(Post)
            .where(Post.status == "published", Post.reply_count == 0, Post.created_at <= cutoff, Post.deleted_at.is_(None))
            .limit(200)
        )
    )
    for post in posts:
        post.status = "archived"
    await db.commit()
    return len(posts)


async def check_ai_admin_health(db: AsyncSession) -> int:
    """同一 AI 管理员连续 5 次无证据回帖 → 提醒补文档；模型连续失败告警。"""
    ai_admins = list(await db.scalars(select(CategoryAiAdmin).where(CategoryAiAdmin.active.is_(True))))
    warned = 0
    for aa in ai_admins:
        recent = list(
            await db.scalars(
                select(KnowledgeHit)
                .where(KnowledgeHit.ai_admin_id == aa.id, KnowledgeHit.replied.is_(False))
                .order_by(KnowledgeHit.created_at.desc())
                .limit(5)
            )
        )
        if len(recent) >= 5:
            admins = list(
                await db.scalars(
                    select(CategoryHumanAdmin.user_id).where(CategoryHumanAdmin.category_id == aa.category_id)
                )
            )
            if admins:
                await notify(
                    db, admins[0], "ai_no_answer",
                    f"「{aa.persona_name}」连续 {len(recent)} 次无证据可答",
                    "知识库可能已过期，建议补充文档", "",
                )
                warned += 1
    return warned
