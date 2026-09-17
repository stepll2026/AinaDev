"""管理：模型配置 CRUD（AES 加密 Key，永不回传明文）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_super_admin
from app.core.security import aes_decrypt, aes_encrypt
from app.models import ModelConfig, User
from app.schemas import ModelConfigIn, ModelConfigOut
from app.services.audit_service import audit
from app.services.llm import LLMConfig

router = APIRouter(prefix="/api/admin/model-configs", tags=["admin-models"])


def _out(mc: ModelConfig) -> ModelConfigOut:
    return ModelConfigOut(
        id=mc.id, name=mc.name, provider=mc.provider, base_url=mc.base_url,
        chat_model=mc.chat_model, embedding_model=mc.embedding_model,
        embedding_dim=mc.embedding_dim, context_length=mc.context_length,
        max_tokens=mc.max_tokens, is_default=mc.is_default, enabled=mc.enabled,
        created_at=mc.created_at, has_api_key=bool(mc.api_key_encrypted),
    )


@router.get("", response_model=list[ModelConfigOut])
async def list_model_configs(admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    rows = list(await db.scalars(select(ModelConfig).where(ModelConfig.deleted_at.is_(None)).order_by(ModelConfig.id)))
    return [_out(m) for m in rows]


@router.post("", response_model=ModelConfigOut)
async def create_model_config(body: ModelConfigIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    if body.is_default:
        await db.execute(update(ModelConfig).where(ModelConfig.deleted_at.is_(None)).values(is_default=False))
    mc = ModelConfig(
        name=body.name, provider=body.provider, base_url=body.base_url,
        api_key_encrypted=aes_encrypt(body.api_key or ""),
        chat_model=body.chat_model, embedding_model=body.embedding_model,
        embedding_dim=body.embedding_dim, context_length=body.context_length,
        max_tokens=body.max_tokens, is_default=body.is_default, enabled=body.enabled,
    )
    db.add(mc)
    await db.commit()
    await db.refresh(mc)
    await audit(db, "user", admin.id, "model_config_create", "model_config", mc.id)
    return _out(mc)


@router.put("/{model_id}", response_model=ModelConfigOut)
async def update_model_config(model_id: int, body: ModelConfigIn, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    mc = await db.get(ModelConfig, model_id)
    if not mc:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    if body.is_default:
        await db.execute(update(ModelConfig).where(ModelConfig.deleted_at.is_(None)).values(is_default=False))
    data = body.model_dump(exclude_unset=True)
    if "api_key" in data:
        api_key = data.pop("api_key")
        if api_key:
            mc.api_key_encrypted = aes_encrypt(api_key)
    for k, v in data.items():
        setattr(mc, k, v)
    await db.commit()
    await audit(db, "user", admin.id, "model_config_update", "model_config", model_id)
    return _out(mc)


@router.delete("/{model_id}")
async def delete_model_config(model_id: int, admin: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone

    mc = await db.get(ModelConfig, model_id)
    if not mc:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    mc.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    await audit(db, "user", admin.id, "model_config_delete", "model_config", model_id)
    return {"ok": True}


@router.post("/test")
async def test_model_config(body: ModelConfigIn, admin: User = Depends(require_super_admin)):
    """连通性测试：用提交的配置发一次最小对话。"""
    from app.services.llm import chat_completion

    cfg = LLMConfig(
        base_url=body.base_url, api_key=body.api_key or "", chat_model=body.chat_model,
        embedding_model=body.embedding_model or body.chat_model, embedding_dim=body.embedding_dim,
    )
    try:
        resp = await chat_completion(cfg, "你是连通性测试助手", "回复：OK", max_tokens=10)
        return {"ok": True, "response": resp[:50]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}
