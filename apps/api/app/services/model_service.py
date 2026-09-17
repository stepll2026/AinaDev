"""模型配置服务：从 DB 读取 LLM 配置（支持栏目级覆盖）。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CategoryAiAdmin, ModelConfig
from app.services.llm import LLMConfig


async def get_default_llm_config(db: AsyncSession) -> LLMConfig:
    mc = await db.scalar(select(ModelConfig).where(ModelConfig.is_default.is_(True), ModelConfig.enabled.is_(True), ModelConfig.deleted_at.is_(None)))
    if not mc:
        mc = await db.scalar(select(ModelConfig).where(ModelConfig.enabled.is_(True), ModelConfig.deleted_at.is_(None)))
    if not mc:
        raise RuntimeError("未配置可用的模型，请在后台『模型配置』中添加")
    from app.core.security import aes_decrypt

    return LLMConfig(
        base_url=mc.base_url,
        api_key=aes_decrypt(mc.api_key_encrypted),
        chat_model=mc.chat_model,
        embedding_model=mc.embedding_model or mc.chat_model,
        embedding_dim=mc.embedding_dim,
        max_tokens=mc.max_tokens,
    )


async def get_ai_admin_llm_config(db: AsyncSession, ai_admin_id: int) -> LLMConfig:
    """AI 管理员专属模型（未配置则用系统默认）。"""
    aa = await db.get(CategoryAiAdmin, ai_admin_id)
    if aa and aa.model_config_id:
        mc = await db.get(ModelConfig, aa.model_config_id)
        if mc and mc.enabled:
            from app.core.security import aes_decrypt

            return LLMConfig(
                base_url=mc.base_url,
                api_key=aes_decrypt(mc.api_key_encrypted),
                chat_model=mc.chat_model,
                embedding_model=mc.embedding_model or mc.chat_model,
                embedding_dim=mc.embedding_dim,
                max_tokens=mc.max_tokens,
            )
    return await get_default_llm_config(db)
