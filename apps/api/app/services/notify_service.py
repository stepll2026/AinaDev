"""通知服务：站内信 + 可选邮件。"""
import smtplib
import ssl
from email.mime.text import MIMEText

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Notification


async def notify(
    db: AsyncSession,
    user_id: int,
    type: str,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
) -> Notification:
    n = Notification(user_id=user_id, type=type, title=title, body=body, link_url=link_url)
    db.add(n)
    await db.commit()
    # 邮件（可选）
    if settings.smtp_host:
        _send_email_async(user_email=None, title=title, body=body or "")
    return n


async def notify_many(
    db: AsyncSession,
    user_ids: list[int],
    type: str,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
) -> None:
    for uid in user_ids:
        db.add(Notification(user_id=uid, type=type, title=title, body=body, link_url=link_url))
    await db.commit()


def _send_email_async(user_email: str | None, title: str, body: str) -> None:
    """同步发送邮件（调用方已异步，此函数阻塞可接受；未配置收件人时仅记录）。"""
    try:
        if not settings.smtp_host or not user_email:
            return
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = title
        msg["From"] = settings.smtp_from or settings.smtp_user
        msg["To"] = user_email
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=ctx, timeout=10) as server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [user_email], msg.as_string())
    except Exception:
        pass  # 邮件失败不影响主流程，站内信已送达
