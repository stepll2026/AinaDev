"""LLM 统一客户端：OpenAI 兼容协议，一份代码适配豆包/通义/DeepSeek/自建 vLLM/Ollama。"""
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import settings


@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    chat_model: str
    embedding_model: str
    embedding_dim: int = 2048
    max_tokens: int = 2048


def default_llm_config() -> LLMConfig:
    return LLMConfig(
        base_url=settings.default_llm_base_url,
        api_key=settings.default_llm_api_key,
        chat_model=settings.default_llm_chat_model,
        embedding_model=settings.default_embedding_model,
        embedding_dim=settings.default_embedding_dim,
    )


def _client(cfg: LLMConfig) -> AsyncOpenAI:
    return AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key or "EMPTY")


async def chat_completion(
    cfg: LLMConfig,
    system_prompt: str,
    user_content: str,
    max_tokens: int | None = None,
    temperature: float = 0.3,
) -> str:
    """单轮对话，返回文本。"""
    client = _client(cfg)
    resp = await client.chat.completions.create(
        model=cfg.chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        max_tokens=max_tokens or cfg.max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


async def chat_with_json(cfg: LLMConfig, system_prompt: str, user_content: str, max_tokens: int = 2048) -> str:
    """强制 JSON 输出（OpenAI 兼容的 response_format）。"""
    client = _client(cfg)
    resp = await client.chat.completions.create(
        model=cfg.chat_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        max_tokens=max_tokens,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or "{}"


async def embed_texts(cfg: LLMConfig, texts: list[str]) -> list[list[float]]:
    """批量 embedding。"""
    if not texts:
        return []
    client = _client(cfg)
    resp = await client.embeddings.create(model=cfg.embedding_model, input=texts)
    # 按输入顺序返回
    ordered = sorted(resp.data, key=lambda d: d.index)
    return [d.embedding for d in ordered]
