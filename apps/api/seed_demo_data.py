# -*- coding: utf-8 -*-
"""模拟初始化数据：用户、知识库文档、帖子、回复、互动。

用法：python seed_demo_data.py
- 依赖本地 API（localhost:8000）与云端库；模型配置（千问）需已就绪。
"""
import asyncio
import io
import json
import os
import random
import sys
import urllib.request

BASE = "http://localhost:8000/api"

# 演示脚本：超管密码从环境变量 ADMIN_PASSWORD 读取（缺省仅限本地演示 admin123456，生产勿用）
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123456")

USERS = [
    ("zhangwei@demo.com", "张伟", "Test123456"),
    ("liting@demo.com", "李婷", "Test123456"),
    ("wangqiang@demo.com", "王强", "Test123456"),
]

DOCS = [
    # (栏目, 文件名, 内容)
    (2, "OntiCards 产品介绍.md",
     """# OntiCards 产品介绍

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
    (3, "社区使用 FAQ.md",
     """# 社区使用 FAQ

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
    (4, "AI 原生运维实践指南.md",
     """# AI 原生运维实践指南

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

POSTS = [
    # (栏目, 标题, 正文, 作者索引, at_ai, tags)
    (1, "社区已支持附件上传", "各位同学：\n\n发帖与回复现已支持上传**图片和文档附件**，支持格式与大小限制可在后台调整。\n\n- 图片：png/jpg/jpeg/gif/webp\n- 文档：pdf/doc/docx/xls/xlsx/txt/md/csv/zip\n- 单文件默认上限 10MB\n\n欢迎体验。", 0, False, ["公告"]),
    (1, "MCP 服务正式开放，豆包工作可接入每日运维", "好消息！社区 MCP 服务已正式开放。\n\n**接入方式**：豆包工作添加 MCP 服务器，URL 为 `{站点}/mcp`，配置 Bearer 令牌后即可调用 15 个运维工具：合规审查、知识库检索、帖子管理、审核处置、每日资讯、周报生成、系统统计等。\n\n后续的每日巡检、周报整理都可以交给智能体自动完成。", 0, False, ["公告", "MCP"]),
    (2, "OntiCards 如何接入社区知识库？", "我们刚部署了 OntiCards，想把产品文档接入社区知识库，让 AI 自动回答客户问题。\n\n管理员在后台上传 PDF/MD 文档到「产品」栏目即可，需要确认：\n1. 文档格式支持哪些？\n2. 索引多久重建一次？\n3. 换了向量模型后怎么办？", 1, True, ["OntiCards", "知识库"]),
    (2, "多数据源接入时权限怎么控制？", "OntiCards 支持 20+ 数据源，但不同团队的数据权限不同。请问接入时是否支持按数据源配置访问白名单？还是说连接串由管理员统一管理即可？", 2, True, ["OntiCards", "权限"]),
    (2, "自然语言取数的准确率如何评估？", "客户想评估 NL2SQL 的准确率，我们准备了几十条测试 SQL。社区 AI 有类似的评测机制吗？比如把测试集灌入知识库后自动跑分？", 1, True, ["NL2SQL", "评测"]),
    (3, "发帖后 AI 一直没回复，是什么原因？", "我在「产品」栏目发了一个问题并勾选了 @AI，但等了好几分钟都没有 AI 回复。\n\n检查过栏目配置是允许自动回复的。后台「Agent 执行记录」里能看到我这条帖子的流水线日志吗？", 2, True, ["AI回复", "排查"]),
    (3, "邀请码过期了怎么办？", "管理员给我生成的邀请码提示已过期，能延长有效期吗？后台是否有配置项？", 1, False, ["邀请码"]),
    (3, "知识库文档支持哪些格式？", "我有一批运维手册是 PDF 和 Word，可以直接上传吗？另外 URL 抓取支持哪些网站？", 2, True, ["知识库", "格式"]),
    (4, "LangGraph 流水线的节点可以单独调试吗？", "我们想复现社区这套「Guardrail→Route→Retrieve→Judge→Generate」流水线，LangGraph 的每个节点能单独调用和调试吗？生产上怎么观测中间状态？", 0, True, ["LangGraph", "流水线"]),
    (4, "无证据不回复的策略怎么配置？", "按设计原则「无证据绝不回帖」，这个阈值在哪里配？不同栏目可以设不同阈值吗？比如产品栏目严格一点 0.8，闲聊 0.5？", 2, True, ["阈值", "配置"]),
]

REPLIES = [
    # (帖子标题匹配, 回复内容, 作者索引)
    ("社区已支持附件上传", "收到，正好可以上传截图反馈问题了。", 1),
    ("社区已支持附件上传", "上传了一张流程图测试一下，显示正常。", 2),
    ("MCP 服务正式开放", "这个太有用了，我准备把每日巡检接进去。", 1),
    ("MCP 服务正式开放", "已接入成功，工具列表 15 个都在。", 2),
    ("邀请码过期了怎么办", "后台邀请码列表里可以重新生成，有效期看系统配置。", 0),
    ("知识库文档支持哪些格式？", "我上传了 PDF 和 MD 都能正常解析，Word 文档建议先转 PDF。", 0),
]


async def api_req(method, path, body=None, token=None, form=None):
    url = f"{BASE}{path}"
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form is not None:
        boundary = "----seeddemo123"
        buf = io.BytesIO()
        for k, v in form:
            if isinstance(v, tuple):  # 文件
                name, filename, content = v
                buf.write(f"--{boundary}\r\n".encode())
                buf.write(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
                buf.write(b"Content-Type: text/markdown\r\n\r\n")
                buf.write(content.encode())
                buf.write(b"\r\n")
            else:
                buf.write(f"--{boundary}\r\n".encode())
                buf.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
                buf.write(str(v).encode())
                buf.write(b"\r\n")
        buf.write(f"--{boundary}--\r\n".encode())
        data = buf.getvalue()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
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


async def main():
    # 0. 登录 admin
    s, d = await api_req("POST", "/auth/login", {"email": "admin@example.com", "password": ADMIN_PASSWORD})
    if s != 200:
        print("登录失败", s, d)
        sys.exit(1)
    token = d["access_token"]
    print("✓ 管理员登录")

    # 1. 创建邀请码并注册 3 个用户
    users_token = []
    for email, name, pwd in USERS:
        s, d = await api_req("POST", "/admin/invitations", {"email": email, "note": f"模拟用户 {name}"}, token)
        if s != 200:
            print(f"  邀请码失败 {email}: {d}")
            continue
        code = d.get("code")
        s, d = await api_req("POST", "/auth/register", {"email": email, "password": pwd, "name": name, "invite_code": code})
        if s == 200:
            users_token.append((email, name, d.get("access_token") or ""))
            print(f"✓ 注册用户 {name} ({email})")
        else:
            print(f"  注册失败 {email}: {s} {d}")

    if not users_token:
        print("!! 没有可用用户，退出")
        return

    # 2. 上传知识库文档（同步处理，等待 embedding）
    for cid, fname, content in DOCS:
        s, d = await api_req("POST", "/admin/rag/upload", None, token, form=[("category_id", cid), ("file", (fname, fname, content))])
        if s != 200:
            print(f"  文档上传失败 {fname}: {d}")
            continue
        doc_id = d["id"]
        s2, d2 = await api_req("POST", f"/admin/rag/{doc_id}/rebuild", {}, token)
        status = d2.get("chunks") if s2 == 200 else d2
        print(f"✓ 知识库文档 {fname} (id={doc_id}) chunks={status}")

    # 3. 发帖
    post_ids = []
    for cid, title, body, ai_idx, at_ai, tags in POSTS:
        email, name, utok = users_token[ai_idx % len(users_token)]
        s, d = await api_req("POST", "/posts", {"category_id": cid, "title": title, "body_md": body, "tags": tags, "at_ai": at_ai}, utok)
        if s == 200:
            post_ids.append(d["id"])
            print(f"✓ 发帖 [{d['id']}] {title} (by {name}, at_ai={at_ai})")
        else:
            print(f"  发帖失败 {title}: {s} {d}")

    # 4. 回复（触发部分 AI 回帖在 trigger 阶段由发帖流水线完成）
    for title_kw, content, ai_idx in REPLIES:
        pid = next((p for p in post_ids if p), None)
        email, name, utok = users_token[ai_idx % len(users_token)]
        # 找到匹配帖子（用标题模糊匹配）
        match = None
        for pid2 in post_ids:
            s, d = await api_req("GET", f"/posts/{pid2}")
            if s == 200 and title_kw in d.get("title", ""):
                match = pid2
                break
        if not match:
            continue
        s, d = await api_req("POST", f"/posts/{match}/replies", {"post_id": match, "body_md": content, "at_ai": False}, utok)
        if s == 200:
            print(f"✓ 回复帖子 {match}（{title_kw}…）")
        else:
            print(f"  回复失败: {s} {d}")

    # 5. 点赞与浏览模拟（随机互动）
    for pid in post_ids[:6]:
        s, d = await api_req("POST", f"/posts/{pid}/like", {}, users_token[random.randint(0, len(users_token) - 1)][2])
        if s == 200:
            print(f"✓ 点赞帖子 {pid}")
    print("\n模拟数据完成。AI 回帖由发帖时触发（at_ai=True 的帖子已进入流水线）。")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop())
