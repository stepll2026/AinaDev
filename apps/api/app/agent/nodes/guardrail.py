"""流水线节点：合规审查。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import PipelineState
from app.models import CategoryHumanAdmin, Post, Reply, User
from app.services.audit_service import audit
from app.services.compliance_service import compliance_check
from app.services.notify_service import notify


async def guardrail_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """① 合规审查：high 自动软隐藏+通知+审计；mid 进审核队列；low/pass 继续。"""
    content = f"{state.get('title', '')}\n{state['body']}"[:8000]
    result = await compliance_check(db, content, state["post_id"], state["trace_id"])
    state["compliance_result"] = result
    severity = result.get("severity", "low")
    passed = result.get("pass", True)

    if severity == "high" or (not passed and severity == "high"):
        # 自动软隐藏 + 通知栏目人类管理员 + 审计
        post = await db.get(Post, state["post_id"])
        if post:
            post.status = "hidden"
            post.human_needed = True
        else:
            reply = await db.get(Reply, state["post_id"])
            if reply:
                reply.status = "hidden"
        await db.commit()
        admins = list(await db.scalars(
            select(CategoryHumanAdmin.user_id).where(CategoryHumanAdmin.category_id == state["category_id"])
        ))
        await notify(
            db, admins[0] if admins else 0,
            "review_status", "内容被合规审查拦截",
            f"合规高风险：{result.get('reason', '')}",
            f"/post/{state['post_id']}",
        ) if admins else None
        await audit(db, "ai_agent", None, "post_hidden_by_compliance", "post", state["post_id"], result)
        state["decision"] = "hidden"
        return state

    if severity == "mid":
        # 进人工审核队列（不公开）
        post = await db.get(Post, state["post_id"])
        if post:
            post.status = "pending_review"
        else:
            reply = await db.get(Reply, state["post_id"])
            if reply:
                reply.status = "pending_review"
        await db.commit()
        state["decision"] = "review"
        return state

    state["decision"] = "pass"
    return state
