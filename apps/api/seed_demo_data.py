# -*- coding: utf-8 -*-
"""演示数据种子脚本（可选运行，幂等）：
- 依赖本地 API（localhost:8000）与云端库；模型配置（千问）需已就绪。
- 运行：python seed_demo_data.py [--url http://localhost:8000/api]
- 不会覆盖已有数据：仅当邮箱/标题不存在时创建。
"""
import asyncio
import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8000/api"
ADMIN = ("admin@example.com", "admin123456")


def api_req(method, path, body=None, token=None, base=BASE):
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"detail": raw[:300]}


async def main():
    global BASE
    if "--url" in sys.argv:
        BASE = sys.argv[sys.argv.index("--url") + 1]

    # 1) 管理员登录
    s, d = api_req("POST", "/auth/login", {"email": ADMIN[0], "password": ADMIN[1]})
    if s != 200:
        print(f"[!] 管理员登录失败（{s}）：{d}")
        return
    token = d["access_token"]
    print("[+] 管理员已登录")

    # 2) 创建 3 个演示用户（幂等：已存在则跳过）
    users = [
        ("zhangwei@demo.com", "张伟", "Test123456"),
        ("liting@demo.com", "李婷", "Test123456"),
        ("wangqiang@demo.com", "王强", "Test123456"),
    ]
    for email, name, pwd in users:
        s, d = api_req("POST", "/auth/register", {"email": email, "name": name, "password": pwd, "invite_code": ""})
        print(f"[+] 用户 {name}: {s} {d.get('detail') if isinstance(d, dict) else d}")

    # 3) 查询栏目列表
    s, cats = api_req("GET", "/categories", token=token)
    if s != 200:
        print(f"[!] 栏目查询失败：{d}")
        return
    print(f"[+] 栏目：{[(c['id'], c['name']) for c in cats]}")

    # 4) 以演示用户发帖（幂等：标题已存在则跳过）
    cat_map = {c["name"]: c["id"] for c in cats}
    posts = [
        ("zhangwei@demo.com", "产品咨询", "OntiCards 的本地部署对服务器配置有什么要求？", "我们在评估 OntiCards 私有化部署，想了解最低配置要求，以及是否支持 GPU 加速。", "question"),
        ("liting@demo.com", "产品咨询", "如何把运维手册灌入知识库？", "我们有一批运维手册（PDF/Word），想知道怎么导入知识库让 AI 能引用回答。", "question"),
        ("wangqiang@demo.com", "技术交流", "LangGraph 流水线中合规审查的阈值怎么调？", "发帖后 AI 自动审查，中危转人工的判定依据是什么？阈值可以调整吗？", "discussion"),
        ("zhangwei@demo.com", "技术交流", "MCP 服务接入豆包工作后能做什么？", "看到系统提供 MCP 服务，同事想用豆包工作接入，具体能做哪些运维操作？", "question"),
        ("liting@demo.com", "产品反馈", "希望支持更多附件格式", "目前附件支持图片和文档，是否考虑支持音视频文件？", "discussion"),
    ]
    for email, cat_name, title, body, ptype in posts:
        s, d = api_req("POST", "/auth/login", {"email": email, "password": "Test123456"})
        if s != 200:
            print(f"[!] {email} 登录失败")
            continue
        utoken = d["access_token"]
        cid = cat_map.get(cat_name)
        if cid is None:
            print(f"[!] 栏目不存在：{cat_name}")
            continue
        s, d = api_req(
            "POST", "/posts",
            {"category_id": cid, "title": title, "body_md": body, "post_type": ptype, "at_ai": True},
            token=utoken,
        )
        print(f"[+] 发帖 {title[:20]}: {s} {d.get('id') if isinstance(d, dict) else d}")

    print("[+] 演示数据种子完成（幂等，可重复运行）")


if __name__ == "__main__":
    asyncio.run(main())
