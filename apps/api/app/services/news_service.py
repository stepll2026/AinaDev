"""每日 AI 资讯：RSS/API 抓取 → LLM 摘要 → 发布到指定栏目。"""
import logging
from datetime import datetime, timezone

import feedparser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiNewsSource, Post, User
from app.services.llm import chat_completion
from app.services.model_service import get_default_llm_config

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """你是企业 AI 资讯编辑。将下列新闻原文压缩为 150-250 字中文摘要，保留核心信息（主体、事件、影响）。
输出纯摘要文本，不要标题、不要列表、不要客套。"""


async def fetch_news_source(db: AsyncSession, source: AiNewsSource) -> list[dict]:
    """抓取单个资讯源，返回 [{title, url, content}]。"""
    items: list[dict] = []
    if source.type == "rss":
        feed = feedparser.parse(source.url)
        for entry in feed.entries[:10]:
            content = entry.get("summary") or entry.get("description") or ""
            items.append({"title": entry.get("title", "").strip(), "url": entry.get("link", ""), "content": content.strip()})
    elif source.type == "api":
        # 通用 JSON 接口：期望 {"data": [{"title":..., "url":..., "content"/"summary":...}]}
        import httpx

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(source.url)
                data = resp.json()
            rows = data.get("data") or data.get("items") or data.get("list") or []
            for row in rows[:10]:
                items.append(
                    {
                        "title": str(row.get("title", "")).strip(),
                        "url": row.get("url") or row.get("link") or "",
                        "content": str(row.get("content") or row.get("summary") or "").strip(),
                    }
                )
        except Exception as e:
            logger.warning("news api fetch failed %s: %s", source.url, e)
    return [i for i in items if i.get("title")]


async def digest_and_publish(db: AsyncSession, source: AiNewsSource) -> int:
    """抓取 → LLM 摘要 → 发布资讯帖（运维 Agent 账号）。返回发布条数。"""
    items = await fetch_news_source(db, source)
    if not items:
        source.last_fetched_at = datetime.now(timezone.utc)
        await db.commit()
        return 0

    # 目标栏目兜底：未配置时自动落到「AI 资讯」栏目（slug=ai-news）
    category_id = source.target_category_id
    if not category_id:
        from app.models import Category
        cat = await db.scalar(select(Category).where(Category.slug == "ai-news"))
        if cat is None:
            raise RuntimeError("未配置资讯栏目（AI 资讯），请在资讯源中指定目标栏目")
        category_id = cat.id

    cfg = await get_default_llm_config(db)
    ops = await db.scalar(select(User).where(User.email == "ops-agent@community.local"))
    author_id = ops.id if ops else 0

    published = 0
    for item in items[:5]:  # 每次最多发布 5 条，避免刷屏
        try:
            summary = await chat_completion(cfg, SUMMARY_PROMPT, item["content"][:4000] or item["title"], max_tokens=600)
        except Exception as e:
            logger.warning("digest failed: %s", e)
            summary = item["content"][:250] or item["title"]

        exists = await db.scalar(select(Post).where(Post.title == item["title"][:250]))
        if exists:
            continue
        body = f"{summary}\n\n> 来源：[{item['title']}]({item['url']})"
        db.add(
            Post(
                category_id=category_id,
                author_id=author_id,
                title=item["title"][:280],
                body_md=body,
                post_type="news",
                status="published",
                tags=["AI 资讯"],
            )
        )
        published += 1
    source.last_fetched_at = datetime.now(timezone.utc)
    await db.commit()
    return published


async def run_daily_news(db: AsyncSession) -> dict:
    """扫描所有启用的资讯源并发布。"""
    sources = list(
        await db.scalars(
            select(AiNewsSource).where(AiNewsSource.enabled.is_(True), AiNewsSource.deleted_at.is_(None))
        )
    )
    total = 0
    for src in sources:
        try:
            total += await digest_and_publish(db, src)
        except Exception as e:
            logger.exception("news source %s failed: %s", src.name, e)
    return {"sources": len(sources), "published": total}
