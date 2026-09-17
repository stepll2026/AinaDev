"""流水线节点：路由。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import PipelineState
from app.models import Category, CategoryAiAdmin


async def route_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """② 路由：是否 @ AI 管理员，或栏目开启自动回帖。"""
    category = await db.get(Category, state["category_id"])
    if not category or not category.auto_reply_enabled:
        state["should_reply"] = False
        return state

    ai_admin = await db.scalar(
        select(CategoryAiAdmin).where(
            CategoryAiAdmin.category_id == state["category_id"],
            CategoryAiAdmin.active.is_(True),
        )
    )
    state["ai_admin_id"] = ai_admin.id if ai_admin else None
    state["ai_admin_name"] = ai_admin.persona_name if ai_admin else None
    state["should_reply"] = ai_admin is not None
    return state
