"""FastAPI 应用入口：启动初始化（表结构/默认栏目/超管/系统账号）+ 路由挂载 + MCP。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.api.router import api_router
from app.config import settings
from app.core.db import Base, engine, SessionLocal
from app.mcp.server import mcp
from app.models import Category, User

logger = logging.getLogger(__name__)


async def init_db_and_defaults() -> None:
    """建表 + 初始化默认数据（幂等，仅首次启动写入）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # 1) 系统账号（公告/运维 Agent）
        from app.services.auth_service import create_system_accounts

        await create_system_accounts(db)

        # 2) 默认模型配置（无则写入，后续后台可改）
        from app.models import ModelConfig

        if not await db.scalar(select(ModelConfig).where(ModelConfig.deleted_at.is_(None))):
            db.add(
                ModelConfig(
                    name="默认模型", provider="openai_compatible",
                    base_url=settings.default_llm_base_url,
                    api_key_encrypted="",
                    chat_model=settings.default_llm_chat_model,
                    embedding_model=settings.default_embedding_model,
                    embedding_dim=settings.default_embedding_dim,
                    context_length=128000, max_tokens=2048,
                    is_default=False, enabled=True,
                )
            )
            logger.info("created default model config")

        # 3) 默认栏目
        if not await db.scalar(select(Category).where(Category.deleted_at.is_(None))):
            defaults = [
                ("announcements", "公告", "版本更新与官方通知", "📣", 0, True, False),
                ("product", "AI 产品交流", "Agent 开发、产品功能讨论", "🤖", 1, True, True),
                ("qa", "使用答疑", "常见问题与技术支持", "❓", 2, True, True),
                ("ai-news", "AI 资讯", "每日 AI 行业资讯（运维 Agent 自动发布）", "📰", 3, False, True),
            ]
            for slug, name, desc, icon, sort, allow, auto in defaults:
                db.add(
                    Category(
                        slug=slug, name=name, description=desc, icon=icon,
                        sort_order=sort, allow_post=allow, auto_reply_enabled=auto,
                    )
                )
            logger.info("created default categories")

        # 4) 超管：环境变量指定 或 首个注册用户自动成为超管（在 register 处处理）
        admin_email = getattr(settings, "admin_email", "")
        if admin_email:
            if not await db.scalar(select(User).where(User.email == admin_email.lower())):
                import secrets as _secrets

                from app.core.security import hash_password

                admin_pwd = getattr(settings, "admin_password", "") or _secrets.token_urlsafe(12)
                db.add(
                    User(
                        email=admin_email.lower(), name=getattr(settings, "admin_name", "管理员"),
                        password_hash=hash_password(admin_pwd),
                        account_type="human", role="super_admin", status="active",
                    )
                )
                logger.warning(
                    "created super admin from env: %s（未配置 ADMIN_PASSWORD，已生成随机密码：%s，请立即保存并登录修改）",
                    admin_email, admin_pwd,
                )
        await db.commit()


# MCP Server（豆包工作等 MCP 客户端接入，URL: /mcp）
mcp_app = mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_and_defaults()
    logger.info("ai-native-community API started")
    yield
    logger.info("ai-native-community API stopped")


app = FastAPI(title="AI 原生开发者社区 API", version="1.0.0", lifespan=lifespan)
app.mount("/mcp", mcp_app)
app.include_router(api_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "site": settings.site_name, "mcp_endpoint": "/mcp"}
