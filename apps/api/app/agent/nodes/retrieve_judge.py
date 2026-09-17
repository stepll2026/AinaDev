"""流水线节点：RAG 混合检索 + 证据判定。"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import PipelineState
from app.models import AgentRun, KnowledgeHit
from app.services.rag_service import fetch_chunks, hybrid_search


async def retrieve_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """③ RAG 混合检索（仅本栏目命名空间）+ ④ 证据判定。"""
    query = f"{state.get('title', '')}\n{state['body']}"[:2000]
    start = time.time()
    ranked = await hybrid_search(db, state["category_id"], query, top_k=5, vector_top=20, fts_top=20)
    latency = int((time.time() - start) * 1000)

    top1_score = ranked[0]["score"] if ranked else 0.0
    chunk_ids = [r["chunk_id"] for r in ranked]
    chunks = await fetch_chunks(db, chunk_ids)

    chunk_list = [
        {"chunk_id": c.id, "doc_id": c.document_id, "title": c.title, "content": c.content[:1500], "filename": (c.meta_data or {}).get("filename")}
        for c in chunks
    ]
    state["chunks"] = chunk_list
    state["top1_score"] = top1_score

    # 记录 AgentRun（retrieve）
    db.add(
        AgentRun(
            trace_id=state["trace_id"], trigger_type="retrieve", post_id=state["post_id"],
            category_id=state["category_id"], ai_admin_id=state.get("ai_admin_id"),
            node="retrieve", latency_ms=latency,
            decision="retrieved" if ranked else "empty",
            score=top1_score, detail={"chunk_ids": chunk_ids, "ranked_scores": ranked},
        )
    )
    await db.commit()
    return state


async def judge_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """④ 证据判定：top1_score < 阈值 → 不回帖。"""
    threshold = state.get("reply_threshold", 0.7)
    hit = KnowledgeHit(
        post_id=state["post_id"],
        ai_admin_id=state.get("ai_admin_id"),
        retrieved_chunks=state["chunks"],
        top_score=state["top1_score"],
        replied=state["top1_score"] >= threshold,
    )
    db.add(hit)
    await db.commit()

    if state["top1_score"] < threshold:
        # 铁律：无证据不回帖
        state["decision"] = "no_evidence"
        state["human_needed"] = True
        # 通知人类管理员补文档
        from sqlalchemy import select as sa_select
        from app.models import Category, CategoryHumanAdmin
        from app.services.notify_service import notify

        category = await db.get(Category, state["category_id"])
        if category and category.notify_human_on_no_evidence:
            admins = list(await db.scalars(
                sa_select(CategoryHumanAdmin.user_id).where(CategoryHumanAdmin.category_id == state["category_id"])
            ))
            if admins:
                await notify(
                    db, admins[0], "ai_no_answer",
                    f"「{state.get('ai_admin_name') or 'AI 管理员'}」无证据可答，建议补文档",
                    f"相似度 {state['top1_score']:.2f} 低于阈值 {threshold}，点击查看帖子",
                    f"/post/{state['post_id']}",
                )
        db.add(
            AgentRun(
                trace_id=state["trace_id"], trigger_type="judge", post_id=state["post_id"],
                category_id=state["category_id"], ai_admin_id=state.get("ai_admin_id"),
                node="judge", decision="no_evidence", score=state["top1_score"],
            )
        )
        await db.commit()
    else:
        state["decision"] = "generate"
    return state
