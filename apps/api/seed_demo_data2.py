# -*- coding: utf-8 -*-
"""模拟数据补充：知识库文档（DB 直插+同步向量化）+ 修正帖子弹 + AI 回帖验证。"""
import asyncio
import json
import selectors
import sys
import urllib.request

BASE = "http://localhost:8000/api"

DOCS = [
    (2, "OntiCards 产品介绍.md", "md", """# OntiCards 产品介绍

OntiCards 是一款面向企业的 AI 原生数据智能产品，定位为"卡片式智能体工作台"。

## 核心能力

1. **智能体卡片**：把数据分析、知识问答、报表生成封装为可编排的 Agent 卡片，业务人员无需写代码即可搭建自动化工作流。
2. **多源数据接入**：支持 PostgreSQL、MySQL、飞书表格、API 接口等 20+ 数据源，实时同步与定时增量。
3. **自然语言取数**：用户用中文提问即可得到 SQL 与图表，支持追问与结果解释。
4. **MCP 协议支持**：可通过 MCP 接入豆包工作、飞书等外部智能体生态，实现跨平台自动化运维。

## 典型场景

- 运营周报自动生成：每日凌晨拉取业务数据，自动生成图文周报并推送群聊。
- 异常指标监控：设定阈值后自动巡检核心指标，异常时触发告警卡片。
- 知识库问答：把产品文档、FAQ 灌入知识库，回答员工与客户的常见问题。

## 部署方式

支持 Docker Compose 单机部署与 Kubernetes 集群部署，私有化数据不出内网。"""),
    (3, "社区使用 FAQ.md", "md", """# 社区使用 FAQ

## 如何注册账号？

社区采用邀请制。管理员在后台「审核 / 资讯 / 用户」页签生成邀请码，新用户凭邀请码注册。

## AI 会自动回复我的帖子吗？

会。发帖时勾选「@ 栏目 AI 管理员」，系统将自动执行：合规审查 → 知识库检索 → 证据判定 → AI 生成回复。AI 只在检索到足够相关证据（相似度 ≥ 栏目阈值，默认 0.7）时才会回复，且回复会附上引用来源。

## 为什么我的帖子没有 AI 回复？

可能原因：未勾选 @ AI 管理员；栏目关闭了自动回复；知识库中没有相关证据；或帖子被合规审查拦截。管理员可在「Agent 执行记录」查看完整决策链路。

## 支持哪些附件格式？

图片（png/jpg/jpeg/gif/webp）、文档（pdf/doc/docx/xls/xlsx/txt/md/csv）、压缩包（zip）。单文件默认不超过 10MB，管理员可在「审计 & 设置」页调整。

## 如何举报违规内容？

帖子与回复均可举报，管理员在后台审核队列处理。"""),
    (4, "AI 原生运维实践指南.md", "md", """# AI 原生运维实践指南

## 背景

传统运维以"人盯屏幕"为主：告警靠人看、问题靠人查、周报靠人写。AI 原生运维的核心是把可重复的判断交给 AI 流水线，人只处理 AI 无法确定的部分。

## 落地路径

1. **事件即触发**：社区发帖、系统告警、工单创建等事件自动进入 LangGraph 流水线。
2. **流水线分级**：合规审查（Guardrail）→ 意图路由（Route）→ 知识检索（Retrieve）→ 证据判定（Judge）→ 生成回复（Generate）→ 后处理（Postprocess）。每一步决策落审计日志。
3. **无证据不回复**：Judge 节点相似度低于阈值（默认 0.7）时不生成 AI 回复，转人工或明确告知用户"知识库暂无证据"。
4. **人机协作**：AI 自评置信度低于阈值（默认 0.6）时标记需要人工复核。

## 案例：社区智能问答

某客户把产品手册、FAQ 共 200 篇文档灌入知识库。员工提问后，流水线检索 top5 证据、判定得分 0.82 ≥ 0.7，AI 生成带引用的回复。整个链路 4.2 秒，人工干预为零。

## 注意事项

- 知识库文档质量决定 AI 回复质量，建议定期重建索引（换模型后必须重建）。
- 模型 Key 在后台「模型配置」页配置，AES 加密存储，永不回传明文。"""),
]


def api_req(method, path, body=None, token=None):
    url = f"{BASE}{path}"
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read().decode(errors="replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")[:300]
    except Exception as e:
        return -1, repr(e)[:200]


async def seed_docs_via_db():
    """DB 直插文档 + 同步 process_document（向量化）。"""
    from pathlib import Path

    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import RagDocument
    from app.services.document_service import process_document

    seed_dir = Path("uploads/seed_docs")
    seed_dir.mkdir(parents=True, exist_ok=True)

    async with SessionLocal() as db:
        for cid, fname, ftype, content in DOCS:
            exists = await db.scalar(select(RagDocument.id).where(RagDocument.filename == fname, RagDocument.deleted_at.is_(None)))
            if exists:
                print(f"  跳过（已存在）{fname}")
                continue
            path = seed_dir / fname
            path.write_text(content, encoding="utf-8")
            doc = RagDocument(
                category_id=cid, filename=fname, file_type=ftype,
                storage_path=str(path), status="parsing", uploader_id=1,
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)
            try:
                await process_document(db, doc.id)
                await db.refresh(doc)
                print(f"✓ 文档 {fname} (id={doc.id}) chunks={doc.chunk_count} status={doc.status}")
            except Exception as e:
                doc.status = "failed"
                doc.error = str(e)[:200]
                await db.commit()
                print(f"  ✗ 文档处理失败 {fname}: {e}")


async def main():
    # 登录 admin
    s, d = api_req("POST", "/auth/login", {"email": "admin@example.com", "password": "admin123456"})
    if s != 200:
        print("登录失败", s, d)
        return
    token = d["access_token"]
    print("✓ 管理员登录")

    # 1. 知识库文档（DB 直插）
    await seed_docs_via_db()

    # 2. 补发两条原 AI 资讯栏目帖子（改发问答栏目 id=3）
    extra_posts = [
        (3, "LangGraph 流水线的节点可以单独调试吗？",
         "我们想复现社区这套「Guardrail→Route→Retrieve→Judge→Generate」流水线，LangGraph 的每个节点能单独调用和调试吗？生产上怎么观测中间状态？",
         ["LangGraph", "流水线"], True),
        (3, "无证据不回复的策略怎么配置？",
         "按设计原则「无证据绝不回帖」，这个阈值在哪里配？不同栏目可以设不同阈值吗？比如产品栏目严格一点 0.8，问答栏目宽松 0.6？",
         ["阈值", "配置"], True),
    ]
    # 用李婷的 token
    s, d = api_req("POST", "/auth/login", {"email": "liting@demo.com", "password": "Test123456"})
    utok = d["access_token"] if s == 200 else token
    for cid, title, body, tags, at_ai in extra_posts:
        s, d = api_req("POST", "/posts", {"category_id": cid, "title": title, "body_md": body, "tags": tags, "at_ai": at_ai}, utok)
        print(f"{'✓' if s == 200 else '✗'} 发帖 [{d.get('id') if s == 200 else '-'}] {title} -> {s}")
        if s != 200:
            print("   ", d)

    # 3. AI 回帖验证：手动触发流水线（本地无 worker，同步执行）
    from sqlalchemy import text

    from app.agent.runner import trigger_pipeline
    from app.core.db import SessionLocal

    async with SessionLocal() as db:
        rows = (await db.execute(text("SELECT id, title FROM posts WHERE id IN (7,8,9,10,12) ORDER BY id"))).all()
        for pid, title in rows:
            try:
                trace = await trigger_pipeline(db, pid, "post")
                print(f"✓ 触发 AI 流水线 帖子 {pid}（{title[:20]}…） trace={trace}")
            except Exception as e:
                print(f"  ✗ 流水线失败 帖子 {pid}: {str(e)[:200]}")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
