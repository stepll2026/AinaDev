"""合规审查：LLM 审查（提示词后台可配置）+ 内置通用词表预检。"""
import json
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, SiteConfig
from app.services.llm import chat_with_json
from app.services.model_service import get_default_llm_config

# 内置通用风险词表（本地预检兜底，最终以 LLM 审查为准；可被站点配置 review_prompt 增强）
COMMON_BLOCK_WORDS = [
    "枪支", "爆炸物", "制毒", "贩毒", "博彩", "赌博平台", "代开发票", "刷单兼职",
]

# 默认审核提示词（后台「设置」页可修改，覆盖后立即生效）
DEFAULT_REVIEW_PROMPT = """你是企业内部开发者社区的内容安全审核员。请审核用户发布的帖子/回复，输出严格 JSON：
{"pass": true/false, "reason": "简要原因", "severity": "low|mid|high"}

以下内容一律判定为不通过（pass=false，severity 按危险程度给 mid 或 high）：
1. 政治敏感：攻击中国政府、中国共产党、领导人，或提及敏感政治事件、敏感人物（含谐音、影射、藏头诗、拆字等变体）。
2. 违法与高危：枪支、爆炸物、毒品、赌博、诈骗、黑客攻击教程、泄露国家秘密或企业机密。
3. 色情低俗：色情描写、色情链接、性暗示、招嫖。
4. 暴力恐怖：暴力威胁、恐吓、教唆伤害他人、恐怖主义言论。
5. 人身攻击与仇恨：辱骂、诅咒、歧视（性别/地域/民族/宗教/疾病）、贬低他人人格。
6. 粗口脏话：任何不文明用语，无论是否用谐音、缩写、拼音、emoji 变体。
7. 消极负面情绪宣泄：与工作无关的抱怨、消极怠工言论、影响团队氛围的负能量。
8. 与技术无关的闲聊灌水：拉家常、灌水、广告推广、刷屏、无关内容。
9. 其他企业内网不应出现的内容。

正常的技术讨论（含批评某产品/某 API 不好用、求助、经验分享）属于合规内容，不要误判。
只依据给定内容判断，不要联想扩展。"""


async def get_review_prompt(db: AsyncSession) -> str:
    """读取后台配置的审核提示词，未配置时用默认预设。"""
    row = await db.scalar(select(SiteConfig).where(SiteConfig.key == "review_prompt"))
    if row and row.value.strip():
        return row.value.strip()
    return DEFAULT_REVIEW_PROMPT


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
    system_prompt = await get_review_prompt(db)
    user_content = f"待审查内容：\n{content[:4000]}\n\n本地预检命中词：{hit_word or '无'}"

    start = time.time()
    raw = ""
    try:
        raw = await chat_with_json(cfg, system_prompt, user_content)
        result = json.loads(raw)
        if not isinstance(result, dict) or "pass" not in result:
            raise ValueError("缺少 pass 字段")
    except Exception as exc:
        # AI 不返回 / 异常 / 输出非法 JSON / 缺字段：保守策略判定不通过，转人工复核
        result = {
            "pass": False,
            "reason": "AI 审核未返回有效结果（超时/异常/格式错误），已按不通过处理，转人工复核",
            "severity": "mid",
        }
        raw = raw or f"<error:{type(exc).__name__}>"

    # 预检命中高危词且 LLM 未识别时，提升为 mid（不误杀，转人工）
    if hit_word and result.get("pass", True):
        result = {"pass": False, "reason": f"命中敏感词「{hit_word}」，转人工复核", "severity": "mid"}

    db.add(
        AgentRun(
            trace_id=trace_id,
            trigger_type="compliance",
            post_id=post_id,
            node="guardrail",
            prompt=system_prompt + "\n---\n" + user_content,
            response=raw,
            latency_ms=int((time.time() - start) * 1000),
            decision=result.get("severity", "low"),
            score=None,
        )
    )
    await db.commit()
    return result
