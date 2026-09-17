"""MCP Server：向豆包工作等 MCP 客户端暴露社区运维工具集。

同事接入方式：MCP 客户端 → 服务器 URL https://<host>/mcp，传输类型 HTTP，
自定义 Headers：Authorization: Bearer <MCP_API_KEY>（超管可在站点配置中查看/修改）。
"""
import logging
from typing import Any

from fastmcp import FastMCP

from app.core.db import SessionLocal

logger = logging.getLogger(__name__)

mcp = FastMCP("ai-native-community-ops", instructions="企业 AI 开发者社区运维工具集：内容审查、知识库检索、帖子/栏目管理、审核处置、资讯与周报运维。")


# ---------- 工具：内容与知识库 ----------
@mcp.tool()
async def compliance_check(content: str) -> dict[str, Any]:
    """对一段内容做合规审查（LLM + 词表），返回 pass/severity/reason。适用于发帖前预检或批量扫描。"""
    from app.services.compliance_service import compliance_check as _check

    async with SessionLocal() as db:
        return await _check(db, content[:8000], None, "mcp-triggered")


@mcp.tool()
async def rag_search(category_id: int, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """在指定栏目知识库中做 RAG 混合检索（向量+全文+RRF），返回证据 chunk。"""
    from app.services.rag_service import fetch_chunks, hybrid_search

    async with SessionLocal() as db:
        ranked = await hybrid_search(db, category_id, query, top_k=top_k, vector_top=20, fts_top=20)
        chunks = await fetch_chunks(db, [r["chunk_id"] for r in ranked])
        return [
            {
                "chunk_id": c.id, "document_id": c.document_id, "category_id": c.category_id,
                "content": c.content[:1500], "filename": (c.meta_data or {}).get("filename"),
                "score": next((r["score"] for r in ranked if r["chunk_id"] == c.id), 0.0),
            }
            for c in chunks
        ]


@mcp.tool()
async def rag_list_documents(category_id: int | None = None) -> list[dict[str, Any]]:
    """列出知识库文档及处理状态（parsing/processing/ready/failed）、chunk 数。"""
    from sqlalchemy import select

    from app.models import RagDocument

    async with SessionLocal() as db:
        stmt = select(RagDocument).where(RagDocument.deleted_at.is_(None))
        if category_id:
            stmt = stmt.where(RagDocument.category_id == category_id)
        docs = list(await db.scalars(stmt.order_by(RagDocument.created_at.desc())))
        return [
            {"id": d.id, "category_id": d.category_id, "filename": d.filename, "file_type": d.file_type,
             "status": d.status, "chunk_count": d.chunk_count, "enabled": d.enabled, "error": d.error}
            for d in docs
        ]


# ---------- 工具：栏目 / 帖子 ----------
@mcp.tool()
async def list_categories() -> list[dict[str, Any]]:
    """列出所有栏目（含是否开启自动回帖、AI 管理员、阈值）。"""
    from sqlalchemy import select

    from app.models import Category, CategoryAiAdmin

    async with SessionLocal() as db:
        cats = list(await db.scalars(select(Category).where(Category.deleted_at.is_(None)).order_by(Category.sort_order)))
        result = []
        for c in cats:
            aa = await db.scalar(select(CategoryAiAdmin).where(CategoryAiAdmin.category_id == c.id, CategoryAiAdmin.active.is_(True)))
            result.append(
                {"id": c.id, "slug": c.slug, "name": c.name, "description": c.description,
                 "auto_reply_enabled": c.auto_reply_enabled, "reply_threshold": c.reply_threshold,
                 "ai_admin": aa.persona_name if aa else None}
            )
        return result


@mcp.tool()
async def search_posts(query: str, category_id: int | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """全文搜索帖子（标题+正文），返回标题、链接、状态。"""
    from sqlalchemy import or_, select

    from app.models import Post

    async with SessionLocal() as db:
        stmt = select(Post).where(Post.status == "published", Post.deleted_at.is_(None))
        stmt = stmt.where(or_(Post.title.ilike(f"%{query}%"), Post.body_md.ilike(f"%{query}%")))
        if category_id:
            stmt = stmt.where(Post.category_id == category_id)
        rows = list(await db.scalars(stmt.order_by(Post.created_at.desc()).limit(limit)))
        return [
            {"post_id": p.id, "title": p.title, "category_id": p.category_id,
             "reply_count": p.reply_count, "created_at": str(p.created_at), "link": f"/post/{p.id}"}
            for p in rows
        ]


@mcp.tool()
async def get_post(post_id: int) -> dict[str, Any]:
    """查看帖子详情（含回复数、AI 是否已处理）。"""
    from sqlalchemy import select

    from app.models import Post, Reply

    async with SessionLocal() as db:
        post = await db.get(Post, post_id)
        if not post:
            return {"error": "帖子不存在"}
        replies = list(await db.scalars(select(Reply).where(Reply.post_id == post_id, Reply.deleted_at.is_(None)).order_by(Reply.created_at)))
        return {
            "post_id": post.id, "title": post.title, "body": post.body_md, "status": post.status,
            "tags": post.tags, "ai_handled": post.ai_handled, "human_needed": post.human_needed,
            "reply_count": post.reply_count, "created_at": str(post.created_at),
            "replies": [{"id": r.id, "author_type": r.author_type, "body": r.body_md, "status": r.status, "citations": r.citations} for r in replies],
        }


# ---------- 工具：审核与处置 ----------
@mcp.tool()
async def get_review_queue() -> list[dict[str, Any]]:
    """获取审核队列（合规中危帖、低置信 AI 回复、用户举报）。"""
    from sqlalchemy import select

    from app.models import Post, Reply, Report, User

    async with SessionLocal() as db:
        items: list[dict[str, Any]] = []
        posts = list(await db.scalars(select(Post).where(Post.status == "pending_review", Post.deleted_at.is_(None)).limit(50)))
        for p in posts:
            items.append({"kind": "post_mid", "id": p.id, "title": p.title, "body": p.body_md[:300], "created_at": str(p.created_at)})
        replies = list(await db.scalars(select(Reply).where(Reply.status == "pending_review", Reply.deleted_at.is_(None)).limit(50)))
        for r in replies:
            items.append({"kind": "reply_low_conf", "id": r.id, "body": r.body_md[:300], "created_at": str(r.created_at)})
        reports = list(await db.scalars(select(Report).where(Report.status == "open").limit(50)))
        for rep in reports:
            items.append({"kind": "report", "id": rep.id, "target_type": rep.target_type, "target_id": rep.target_id, "reason": rep.reason})
        return items


@mcp.tool()
async def review_action(kind: str, id: int, action: str, resolution: str | None = None) -> dict[str, Any]:
    """处置审核项。kind: post_mid/reply_low_conf/report；action: approve/hide/delete/warn/dismiss。"""
    from app.models import Post, Reply, Report
    from app.services.audit_service import audit

    async with SessionLocal() as db:
        if kind == "post_mid":
            post = await db.get(Post, id)
            if not post:
                return {"error": "帖子不存在"}
            post.status = {"approve": "published", "hide": "hidden", "delete": "deleted"}.get(action, post.status)
            await db.commit()
            await audit(db, "ai_agent", None, f"mcp_review_post_{action}", "post", id)
        elif kind == "reply_low_conf":
            reply = await db.get(Reply, id)
            if not reply:
                return {"error": "回复不存在"}
            reply.status = {"approve": "published", "hide": "hidden", "delete": "deleted"}.get(action, reply.status)
            await db.commit()
            await audit(db, "ai_agent", None, f"mcp_review_reply_{action}", "reply", id)
        elif kind == "report":
            rep = await db.get(Report, id)
            if not rep:
                return {"error": "举报不存在"}
            rep.status = "resolved" if action != "dismiss" else "dismissed"
            rep.resolution = resolution or action
            await db.commit()
            await audit(db, "ai_agent", None, f"mcp_report_{action}", "report", id)
        else:
            return {"error": "无效 kind"}
        return {"ok": True, "kind": kind, "id": id, "action": action}


@mcp.tool()
async def moderate_post(post_id: int, action: str, category_id: int | None = None) -> dict[str, Any]:
    """帖子管理操作：pin/unpin、feature/unfeature、lock/unlock、delete、restore、move（需 category_id）。"""
    from datetime import datetime, timezone

    from app.models import Post
    from app.services.audit_service import audit

    async with SessionLocal() as db:
        post = await db.get(Post, post_id)
        if not post:
            return {"error": "帖子不存在"}
        if action in ("pin", "unpin"):
            post.pinned = action == "pin"
        elif action in ("feature", "unfeature"):
            post.featured = action == "feature"
        elif action in ("lock", "unlock"):
            post.locked = action == "lock"
        elif action == "delete":
            post.status = "deleted"
            post.deleted_at = datetime.now(timezone.utc)
        elif action == "restore":
            post.status = "published"
            post.deleted_at = None
        elif action == "move":
            if not category_id:
                return {"error": "缺少目标栏目 category_id"}
            post.category_id = category_id
        else:
            return {"error": f"无效操作 {action}"}
        await db.commit()
        await audit(db, "ai_agent", None, f"mcp_post_{action}", "post", post_id)
        return {"ok": True, "post_id": post_id, "action": action}


# ---------- 工具：资讯与周报运维 ----------
@mcp.tool()
async def run_daily_news() -> dict[str, Any]:
    """立即执行每日 AI 资讯聚合：抓取所有启用的资讯源 → LLM 摘要 → 发布到指定栏目。"""
    from app.services.news_service import run_daily_news

    async with SessionLocal() as db:
        return await run_daily_news(db)


@mcp.tool()
async def run_weekly_report() -> int:
    """生成并推送本周栏目周报给各栏目人类管理员。"""
    from app.services.ops_service import send_weekly_reports

    async with SessionLocal() as db:
        return await send_weekly_reports(db)


@mcp.tool()
async def check_no_reply_48h() -> int:
    """扫描 48h 无回复的帖子并提醒栏目管理员。"""
    from app.services.ops_service import check_no_reply_48h

    async with SessionLocal() as db:
        return await check_no_reply_48h(db)


@mcp.tool()
async def publish_notice(category_id: int, title: str, body: str, tags: list[str] | None = None) -> dict[str, Any]:
    """以官方公告账号发布公告帖（版本更新 Changelog 等）。"""
    from sqlalchemy import select

    from app.models import Post, User

    async with SessionLocal() as db:
        official = await db.scalar(select(User).where(User.email == "official@community.local"))
        if not official:
            return {"error": "官方账号未初始化"}
        post = Post(
            category_id=category_id, author_id=official.id, title=title, body_md=body,
            post_type="announcement", status="published", tags=tags or ["公告"],
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return {"ok": True, "post_id": post.id}


# ---------- 工具：系统状态 ----------
@mcp.tool()
async def get_system_stats() -> dict[str, Any]:
    """系统运行统计：用户/帖子/回复/待审/文档数。"""
    from sqlalchemy import func, select

    from app.models import Post, RagDocument, Reply, Report, User

    async with SessionLocal() as db:
        return {
            "users": await db.scalar(select(func.count(User.id)).where(User.deleted_at.is_(None))) or 0,
            "posts": await db.scalar(select(func.count(Post.id)).where(Post.deleted_at.is_(None))) or 0,
            "replies": await db.scalar(select(func.count(Reply.id)).where(Reply.deleted_at.is_(None))) or 0,
            "pending_reviews": await db.scalar(select(func.count(Post.id)).where(Post.status == "pending_review")) or 0,
            "open_reports": await db.scalar(select(func.count(Report.id)).where(Report.status == "open")) or 0,
            "documents": await db.scalar(select(func.count(RagDocument.id)).where(RagDocument.deleted_at.is_(None))) or 0,
        }


@mcp.tool()
async def recent_agent_runs(limit: int = 10) -> list[dict[str, Any]]:
    """最近 Agent 执行记录（trace 审计，用于排查 AI 回帖异常）。"""
    from sqlalchemy import select

    from app.models import AgentRun

    async with SessionLocal() as db:
        rows = list(await db.scalars(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit)))
        return [
            {"id": r.id, "trace_id": r.trace_id, "node": r.node, "decision": r.decision,
             "score": r.score, "post_id": r.post_id, "latency_ms": r.latency_ms, "created_at": str(r.created_at)}
            for r in rows
        ]
