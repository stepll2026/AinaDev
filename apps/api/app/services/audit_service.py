"""审计日志服务。"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def audit(
    db: AsyncSession,
    actor_type: str,
    actor_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: dict | None = None,
) -> None:
    db.add(AuditLog(actor_type=actor_type, actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, detail=detail))
    await db.commit()
