"""FastAPI 应用入口。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.router import api_router
from app.config import settings
from app.core.db import Base, SessionLocal, engine
from app.mcp.server import mcp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def init_db_and_seed() -> None:
    """建表 + 种子数据。"""
    import app.models  # noqa: F401  确保所有模型注册
    from app.models import Category, ModelConfig, User

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # 1) 系统账号（官方公告 / 运维 Agent）
        from app.services.auth_service import create_system_accounts

        await create_system_accounts(db)

        # 2) 默认模型配置（从环境变量）
        if not await db.scalar(select(ModelConfig).where(ModelConfig.deleted_at.is_(None))):
            from app.core.security import aes_encrypt

            db.add(
                ModelConfig(
                    name="默认模型", provider="openai_compatible",
                    base_url=settings.default_llm_base_url,
                    api_key_encrypted=aes_encrypt(settings.default_llm_api_key or ""),
                    chat_model=settings.default_llm_chat_model,
                    embedding_model=settings.default_embedding_model,
                    embedding_dim=settings.default_embedding_dim,
                    is_default=True, enabled=True,
                )
            )
            logger.info("created default model config (api_key 来自 env 配置)")

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
    # fastmcp 4.x 需要其 lifespan 随父应用启动（session 管理）
    async with mcp_app.lifespan(app):
        await init_db_and_seed()
        yield
        await engine.dispose()


app = FastAPI(title=settings.site_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", settings.public_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 附件静态目录（生产经 nginx /uploads/ 反代）
from pathlib import Path

_upload_dir = Path(settings.upload_dir).resolve()
_upload_dir.mkdir(parents=True, exist_ok=True)
from fastapi.staticfiles import StaticFiles

app.mount("/uploads", StaticFiles(directory=str(_upload_dir)), name="uploads")


@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next):
    """MCP 端点鉴权：Authorization: Bearer <MCP_API_KEY>。"""
    if request.url.path.startswith("/mcp"):
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {settings.mcp_api_key}":
            return JSONResponse({"error": "invalid MCP token"}, status_code=401)
    return await call_next(request)


# MCP Server 挂载（豆包工作等 MCP 客户端接入，URL: /mcp）
app.mount("/mcp", mcp_app)

app.include_router(api_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "site": settings.site_name, "mcp_endpoint": f"{settings.public_base_url}/mcp"}
