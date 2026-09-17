"""合规审查：LLM 审查 + 内置通用词表。"""
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun
from app.services.llm import chat_with_json
from app.services.model_service import get_default_llm_config

# 内置通用风险词表（可被站点配置覆盖，MVP 用通用词表 + LLM 双保险）
COMMON_BLOCK_WORDS = [
    # 违法与高危内容（仅用于本地预检，最终以 LLM 审查为准）
    "枪支", "爆炸物", "制毒", "贩毒", "博彩", "赌博平台", "代开发票", "刷单兼职",
]

SYSTEM_PROMPT = """你是企业开发者社区的内容安全审查员。请审查用户发布的帖子/回复，输出严格 JSON：
{"pass": true/false, "reason": "简要原因", "severity": "low|mid|high"}

审查规则：
1. 违规等级 high：政治敏感、违法内容、人身攻击、仇恨言论、儿童色情、暴力恐怖、涉密信息泄露。
2. 违规等级 mid：广告推广、垃圾灌水、引战争吵、疑似诈骗、未授权转载。
3. 违规等级 low/pass：正常技术交流，含少量无伤大雅的抱怨或情绪。
4. 技术讨论（含批评某产品/某 API 不好用）属于正常内容，不是违规。
只依据给定内容判断，不要联想扩展。"""


async def compliance_check(
    db: AsyncSession,
    content: str,
    post_id: int | None,
    trace_id: str,
) -> dict:
    """返回 {"pass": bool, "reason": str, "severity": str}。"""
    # 0) 本地词表预检（快速拦截，仍走 LLM 确认）
    hit_word = next((w for w in COMMON_BLOCK_WORDS if w in content), None)

    cfg = await get_default_llm_config(db)
    user_content = f"待审查内容：\n{content[:4000]}\n\n本地预检命中词：{hit_word or '无'}"

    import time

    start = time.time()
    raw = await chat_with_json(cfg, SYSTEM_PROMPT, user_content)
    latency = int((time.time() - start) * 1000)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"pass": True, "reason": "审查输出解析失败，默认放行并转人工复核", "severity": "mid"}

    # 预检命中高危词且 LLM 未识别时，提升为 mid（不误杀，转人工）
    if hit_word and result.get("pass", True):
        result = {"pass": False, "reason": f"命中敏感词「{hit_word}」，转人工复核", "severity": "mid"}

    db.add(
        AgentRun(
            trace_id=trace_id,
            trigger_type="compliance",
            post_id=post_id,
            node="guardrail",
            prompt=SYSTEM_PROMPT + "\n---\n" + user_content,
            response=raw,
            latency_ms=latency,
            decision=result.get("severity", "low"),
            score=None,
        )
    )
    await db.commit()
    return result
