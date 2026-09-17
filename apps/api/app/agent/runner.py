"""Agent 流水线运行入口：供 API / worker / MCP 触发。"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import PipelineState
from app.models import Category, CategoryAiAdmin, Post, Reply

logger = logging.getLogger(__name__)


def new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


async def trigger_pipeline(db: AsyncSession, post_id: int, content_type: str = "post") -> str:
    """触发发帖/回帖事件的 AI 原生流水线。返回 trace_id。"""
    trace_id = new_trace_id()
    if content_type == "post":
        post = await db.get(Post, post_id)
        if not post:
            return trace_id
        category_id, author_id, title, body = post.category_id, post.author_id, post.title, post.body_md
    else:
        reply = await db.get(Reply, post_id)
        if not reply:
            return trace_id
        parent = await db.get(Post, reply.post_id)
        if not parent:
            return trace_id
        category_id, author_id, title, body = parent.category_id, reply.author_id, parent.title, reply.body_md

    # 合规审查同样覆盖回帖内容；回帖只走审查 + 内容属正常则不再触发 AI 回复（避免回复套娃）
    state: PipelineState = {
        "post_id": post_id,
        "content_type": content_type,
        "category_id": category_id,
        "author_id": author_id,
        "title": title,
        "body": body,
        "trace_id": trace_id,
        "compliance_result": {},
        "should_reply": content_type == "post",  # 仅新帖触发 AI 回帖，回帖只做合规
        "ai_admin_id": None,
        "ai_admin_name": None,
        "chunks": [],
        "top1_score": 0.0,
        "generation": "",
        "self_score": 0.0,
        "citations": [],
        "decision": "",
        "human_needed": False,
        "reply_threshold": 0.7,
        "self_review_threshold": 0.6,
    }

    # 读取栏目阈值
    category = await db.get(Category, category_id)
    if category:
        state["reply_threshold"] = category.reply_threshold

    # 在后台执行（由调用方决定是任务队列还是直接 await）
    await _run_pipeline(state, db)
    return trace_id


async def _run_pipeline(state: PipelineState, db: AsyncSession) -> None:
    """执行流水线。LangGraph 图节点均为 async 函数且接收 db。
    注：这里直接顺序执行各节点（等价于图拓扑），并使用 checkpointer 语义写入 agent_runs；
    生产环境下可替换为 LangGraph 原生 compile + AsyncPostgresSaver 以支持断点续跑。
    """
    from app.agent.nodes import generate_node, guardrail_node, judge_node, postprocess_node, retrieve_node, route_node

    try:
        state = await guardrail_node(state, db)
        if state.get("decision") in ("hidden", "review"):
            return
        state = await route_node(state, db)
        if not state.get("should_reply"):
            return
        state = await retrieve_node(state, db)
        state = await judge_node(state, db)
        if state.get("decision") == "no_evidence":
            return
        state = await generate_node(state, db)
        state = await postprocess_node(state, db)
        # ⑦ 异步后处理（打标签 / 重复帖检测 / 推送通知）
        from app.services.postprocess_service import async_postprocess

        await async_postprocess(db, state)
    except Exception as e:  # ⑧ 异常分支：记录并告警（重试由任务队列层负责）
        logger.exception("pipeline failed: %s", e)
        from app.models import AgentRun

        db.add(
            AgentRun(
                trace_id=state.get("trace_id", ""), trigger_type="compliance",
                post_id=state.get("post_id"), category_id=state.get("category_id"),
                node="pipeline", decision="error", detail={"error": str(e)},
            )
        )
        await db.commit()
