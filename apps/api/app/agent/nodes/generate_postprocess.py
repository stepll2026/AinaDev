"""流水线节点：生成回帖 + 后处理。"""
import json
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import PipelineState
from app.models import AgentRun, CategoryAiAdmin, Post, Reply, User
from app.services.llm import chat_completion, chat_with_json
from app.services.model_service import get_ai_admin_llm_config


async def generate_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """⑤ 生成：硬约束「只使用下方证据回答，末尾 [1][2] 标注来源；证据不足只输出 NO_ANSWER」+ 自检分。"""
    cfg = await get_ai_admin_llm_config(db, state.get("ai_admin_id") or 0)
    ai_admin = await db.get(CategoryAiAdmin, state.get("ai_admin_id")) if state.get("ai_admin_id") else None

    system = (ai_admin.system_prompt if ai_admin and ai_admin.system_prompt else "你是该栏目 AI 技术支持，只回答与栏目主题相关的问题。")
    if ai_admin and ai_admin.style_prompt:
        system += "\n\n回复风格要求：" + ai_admin.style_prompt
    system += (
        "\n\n【硬约束】只使用下方证据回答，禁止编造。引用末尾用 [1][2] 标注来源序号。"
        "证据不足无法回答时，只输出：NO_ANSWER"
    )

    evidence_lines = []
    for i, c in enumerate(state.get("chunks", []), 1):
        evidence_lines.append(f"[{i}] (文档:{c.get('filename','')}) {c.get('content','')}")
    user_content = (
        f"用户帖子标题：{state.get('title','')}\n用户帖子内容：{state['body']}\n\n"
        f"可用证据：\n" + ("\n".join(evidence_lines) if evidence_lines else "（无证据）") +
        "\n\n请生成回复。若证据不足以回答问题，只输出 NO_ANSWER。"
    )

    start = time.time()
    raw = await chat_completion(cfg, system, user_content)
    latency = int((time.time() - start) * 1000)

    # 自检：LLM 输出一个 0~1 置信分（独立调用）
    self_score = 0.0
    try:
        sraw = await chat_with_json(
            cfg,
            "你是回复质量自检器。根据『问题-证据-回复』判断回复是否忠实于证据：输出 JSON {\"score\": 0.0~1.0}。",
            f"问题：{state.get('title','')}\n证据：{evidence_lines[:3]}\n回复：{raw[:2000]}\n\n"
            f"评分规则：完全基于证据=1.0；部分推断=0.5~0.9；编造或跑题=0.0~0.4。",
            max_tokens=200,
        )
        self_score = float(json.loads(sraw).get("score", 0.0))
    except Exception:
        self_score = 0.0  # 自检失败按低置信处理，进人工队列

    state["generation"] = raw
    state["self_score"] = self_score
    state["citations"] = [
        {"doc_id": c.get("doc_id"), "chunk": c.get("chunk_id"), "title": c.get("filename"), "content": c.get("content")[:300]}
        for c in state.get("chunks", [])
    ]

    db.add(
        AgentRun(
            trace_id=state["trace_id"], trigger_type="generate", post_id=state["post_id"],
            category_id=state["category_id"], ai_admin_id=state.get("ai_admin_id"),
            node="generate", prompt=system + "\n---\n" + user_content, response=raw,
            latency_ms=latency, decision="generated", score=self_score,
        )
    )
    await db.commit()
    return state


async def postprocess_node(state: PipelineState, db: AsyncSession) -> PipelineState:
    """⑥ 后处理：NO_ANSWER 不发帖；自检低分进待审；正常以 AI persona 发布。"""
    generation = state.get("generation", "").strip()
    threshold = state.get("self_review_threshold", 0.6)

    if not generation or "NO_ANSWER" in generation.upper():
        state["decision"] = "no_answer"
        state["human_needed"] = True
        post = await db.get(Post, state["post_id"])
        if post:
            post.human_needed = True
            await db.commit()
        db.add(
            AgentRun(
                trace_id=state["trace_id"], trigger_type="judge", post_id=state["post_id"],
                category_id=state["category_id"], ai_admin_id=state.get("ai_admin_id"),
                node="postprocess", decision="no_answer", score=state.get("self_score", 0.0),
            )
        )
        await db.commit()
        return state

    ai_admin = await db.get(CategoryAiAdmin, state.get("ai_admin_id")) if state.get("ai_admin_id") else None
    author_id = ai_admin.user_id if ai_admin else None
    if not author_id:
        # 兜底：官方账号
        from sqlalchemy import select

        official = await db.scalar(select(User).where(User.email == "official@community.local"))
        author_id = official.id if official else 0

    if state.get("self_score", 0.0) < threshold:
        # 低置信：进待审队列，不公开
        reply = Reply(
            post_id=state["post_id"], author_id=author_id, author_type="ai_admin",
            ai_admin_id=state.get("ai_admin_id"), body_md=generation,
            status="pending_review", citations=state.get("citations"),
        )
        db.add(reply)
        await db.commit()
        state["decision"] = "pending_review"
        db.add(
            AgentRun(
                trace_id=state["trace_id"], trigger_type="judge", post_id=state["post_id"],
                category_id=state["category_id"], ai_admin_id=state.get("ai_admin_id"),
                node="postprocess", decision="pending_review", score=state.get("self_score", 0.0),
            )
        )
        await db.commit()
        return state

    # 正常发布
    reply = Reply(
        post_id=state["post_id"], author_id=author_id, author_type="ai_admin",
        ai_admin_id=state.get("ai_admin_id"), body_md=generation,
        status="published", citations=state.get("citations"),
    )
    db.add(reply)
    post = await db.get(Post, state["post_id"])
    if post:
        post.ai_handled = True
        post.reply_count += 1
    await db.commit()
    state["decision"] = "published"

    db.add(
        AgentRun(
            trace_id=state["trace_id"], trigger_type="generate", post_id=state["post_id"],
            category_id=state["category_id"], ai_admin_id=state.get("ai_admin_id"),
            node="postprocess", decision="published", score=state.get("self_score", 0.0),
            detail={"reply_citations": state.get("citations")},
        )
    )
    await db.commit()
    return state
