"""Agent 执行记录模型（全量审计）。"""
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

TriggerType = Enum(
    "compliance", "route", "retrieve", "judge", "generate", "tagging", "dedup", "news_digest", "weekly_report",
    name="agent_trigger_type",
)


class AgentRun(Base):
    """每次 LLM 调用全量落库：trace_id 串联一次事件流水线的所有节点。"""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    trigger_type: Mapped[str] = mapped_column(TriggerType)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"), nullable=True, index=True)
    reply_id: Mapped[int | None] = mapped_column(ForeignKey("replies.id"), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    ai_admin_id: Mapped[int | None] = mapped_column(ForeignKey("category_ai_admins.id"), nullable=True)
    model_config_id: Mapped[int | None] = mapped_column(ForeignKey("model_configs.id"), nullable=True)
    node: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    decision: Mapped[str | None] = mapped_column(String(100), nullable=True)  # pass/mid/high/replied/no_answer/pending_review/...
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 命中 chunk、重试次数等
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class KnowledgeHit(Base):
    """证据判定结果：是否回帖、命中内容、分数。"""

    __tablename__ = "knowledge_hits"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    ai_admin_id: Mapped[int | None] = mapped_column(ForeignKey("category_ai_admins.id"), nullable=True)
    retrieved_chunks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    top_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    replied: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
