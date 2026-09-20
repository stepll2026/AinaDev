"""每日 AI 资讯：RSS/API 抓取 → 全文转 MD + 图片本地化 → AI 导读 → 发布到指定栏目。"""
import logging
import mimetypes
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup, Tag
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AiNewsSource, Post, User
from app.services.llm import chat_completion
from app.services.model_service import get_default_llm_config

logger = logging.getLogger(__name__)

LEAD_PROMPT = """你是企业 AI 资讯编辑。用 80-120 字中文写一段导读，点出这篇资讯的核心事件与价值（主体、做了什么、为什么重要）。
输出纯导读文本，不要标题、不要列表、不要客套。"""

IMG_MAX_BYTES = 8 * 1024 * 1024
IMG_MAX_PER_ARTICLE = 12
IMG_ALLOWED = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "image/bmp", "image/svg+xml"}


async def _download_image(img_url: str, base_url: str) -> str | None:
    full = urljoin(base_url, img_url)
    if not full.startswith(("http://", "https://")):
        return None
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; AinaBot/1.0)"}) as client:
            resp = await client.get(full)
            if resp.status_code != 200:
                return None
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            if ctype not in IMG_ALLOWED:
                return None
            data = resp.content
            if len(data) > IMG_MAX_BYTES or len(data) < 200:
                return None
            ext = mimetypes.guess_extension(ctype) or ".jpg"
            if ext == ".jpe":
                ext = ".jpg"
            now = datetime.now(timezone.utc)
            rel_dir = Path(f"{now:%Y%m}") / f"{now:%m}"
            target_dir = Path(settings.upload_dir).resolve() / rel_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            stored = f"{uuid.uuid4().hex}{ext}"
            (target_dir / stored).write_bytes(data)
            return f"/uploads/{rel_dir.as_posix()}/{stored}"
    except Exception as e:
        logger.warning("image download failed %s: %s", full, e)
        return None


def _inline_text(el: Tag) -> str:
    out = ""
    for node in el.children:
        if isinstance(node, str):
            out += node
        elif node.name in ("strong", "b"):
            out += f"**{node.get_text(strip=True)}**"
        elif node.name in ("em", "i"):
            out += f"*{node.get_text(strip=True)}*"
        elif node.name == "a":
            href = node.get("href", "")
            txt = node.get_text(strip=True)
            if href and txt:
                out += f"[{txt}]({href})"
            else:
                out += txt
        elif node.name == "br":
            out += "  \n"
        else:
            out += node.get_text()
    return re.sub(r"\s+", " ", out).strip()


async def html_to_markdown(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "iframe", "noscript"]):
        t.decompose()
    img_count = 0
    lines: list[str] = []
    for el in soup.children:
        if isinstance(el, str):
            txt = el.strip()
            if txt:
                lines.append(txt)
            continue
        if not isinstance(el, Tag):
            continue
        name = el.name.lower()
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(name[1])
            lines.append("\n" + "#" * (level + 1) + " " + el.get_text(strip=True))
        elif name == "p":
            for img in el.find_all("img"):
                if img_count >= IMG_MAX_PER_ARTICLE:
                    img.decompose()
                    continue
                src = img.get("src") or img.get("data-src") or ""
                if src:
                    local = await _download_image(src, base_url)
                    img_count += 1
                    if local:
                        img.replace_with(f"\n\n![{img.get('alt','')}]({local})\n\n")
                    else:
                        img.decompose()
            txt = _inline_text(el)
            if txt:
                lines.append(txt)
        elif name in ("ul", "ol"):
            for i, li in enumerate(el.find_all("li", recursive=False), 1):
                bullet = f"{i}. " if name == "ol" else "- "
                lines.append(bullet + _inline_text(li))
        elif name == "blockquote":
            for line in el.get_text("\n").strip().splitlines():
                lines.append("> " + line.strip())
        elif name in ("pre",):
            code = el.get_text()
            lines.append(f"\n```\n{code.strip()}\n```")
        elif name == "figure":
            img = el.find("img")
            if img and img_count < IMG_MAX_PER_ARTICLE:
                src = img.get("src") or img.get("data-src") or ""
                if src:
                    local = await _download_image(src, base_url)
                    img_count += 1
                    if local:
                        lines.append(f"\n\n![]({local})\n\n")
            cap = el.find("figcaption")
            if cap:
                lines.append(f"*{cap.get_text(strip=True)}*")
        elif name == "img":
            if img_count < IMG_MAX_PER_ARTICLE:
                src = el.get("src") or el.get("data-src") or ""
                if src:
                    local = await _download_image(src, base_url)
                    img_count += 1
                    if local:
                        lines.append(f"\n\n![]({local})\n\n")
        elif name in ("div", "section", "article"):
            sub = await html_to_markdown(el.decode_contents(), base_url)
            if sub.strip():
                lines.append(sub)
        else:
            txt = _inline_text(el)
            if txt:
                lines.append(txt)
    md = "\n\n".join(l.strip() for l in lines if l.strip())
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


async def _fetch_fulltext(url: str) -> str:
    import asyncio

    def _extract() -> str:
        try:
            import trafilatura
            from bs4 import BeautifulSoup
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return ""
            soup = BeautifulSoup(downloaded, "html.parser")
            body = soup.find("article") or soup.find("main")
            if body:
                return body.decode_contents()
            return trafilatura.extract(downloaded, output_format="html") or ""
        except Exception as e:
            logger.warning("fulltext extract %s failed: %s", url, e)
            return ""

    return await asyncio.to_thread(_extract)


async def fetch_news_source(db: AsyncSession, source: AiNewsSource) -> list[dict]:
    items: list[dict] = []
    if source.type == "rss":
        feed = feedparser.parse(source.url)
        for entry in feed.entries[:10]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            raw_html = ""
            if entry.get("content"):
                raw_html = entry["content"][0].get("value", "")
            if not raw_html:
                raw_html = entry.get("summary") or entry.get("description") or ""
            if len(re.sub(r"<[^>]+>", "", raw_html)) < 500 and link:
                full = await _fetch_fulltext(link)
                if len(re.sub(r"<[^>]+>", "", full)) > len(re.sub(r"<[^>]+>", "", raw_html)):
                    raw_html = full
            items.append({"title": title, "url": link, "html": raw_html})
    elif source.type == "api":
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(source.url)
                data = resp.json()
            rows = data.get("data") or data.get("items") or data.get("list") or []
            for row in rows[:10]:
                items.append({"title": str(row.get("title", "")).strip(), "url": row.get("url") or row.get("link") or "", "html": str(row.get("content") or row.get("summary") or "")})
        except Exception as e:
            logger.warning("news api fetch failed %s: %s", source.url, e)
    result: list[dict] = []
    for i in items:
        if not i.get("title"):
            continue
        try:
            md = await html_to_markdown(i.get("html", ""), i.get("url") or source.url)
        except Exception as e:
            logger.warning("html->md failed for %s: %s", i["url"], e)
            md = re.sub(r"<[^>]+>", "", i.get("html", ""))
        result.append({"title": i["title"], "url": i["url"], "content_md": md})
    return result


async def digest_and_publish(db: AsyncSession, source: AiNewsSource) -> int:
    items = await fetch_news_source(db, source)
    if not items:
        source.last_fetched_at = datetime.now(timezone.utc)
        await db.commit()
        return 0
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
    for item in items[:5]:
        exists = await db.scalar(select(Post).where(Post.title == item["title"][:250], Post.deleted_at.is_(None)))
        if exists:
            continue
        lead = ""
        try:
            lead = await chat_completion(cfg, LEAD_PROMPT, item["content_md"][:4000] or item["title"], max_tokens=200)
            lead = lead.strip()
        except Exception as e:
            logger.warning("lead digest failed: %s", e)
        body_parts = []
        if lead:
            body_parts.append(f"> 📰 **导读**：{lead}\n")
        if item["content_md"]:
            body_parts.append(item["content_md"])
        body_parts.append(f"\n---\n> 原文链接：[{item['title']}]({item['url']})")
        body = "\n\n".join(body_parts)
        db.add(Post(category_id=category_id, author_id=author_id, title=item["title"][:280], body_md=body, post_type="news", status="published", tags=["AI 资讯"]))
        published += 1
    source.last_fetched_at = datetime.now(timezone.utc)
    await db.commit()
    return published


async def run_daily_news(db: AsyncSession) -> dict:
    sources = list(await db.scalars(select(AiNewsSource).where(AiNewsSource.enabled.is_(True), AiNewsSource.deleted_at.is_(None))))
    total = 0
    for src in sources:
        try:
            total += await digest_and_publish(db, src)
        except Exception as e:
            logger.exception("news source %s failed: %s", src.name, e)
    return {"sources": len(sources), "published": total}
