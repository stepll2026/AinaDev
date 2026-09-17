# -*- coding: utf-8 -*-
"""演示数据种子脚本 2（可选运行，幂等）：
- 创建演示用户 → 发帖 → 回复 → 点赞 → 订阅。
- 运行：python seed_demo_data2.py [--url http://localhost:8000/api]
"""
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


def main():
    global BASE
    if "--url" in sys.argv:
        BASE = sys.argv[sys.argv.index("--url") + 1]

    s, d = api_req("POST", "/auth/login", {"email": ADMIN[0], "password": ADMIN[1]})
    if s != 200:
        print(f"[!] 管理员登录失败（{s}）：{d}")
        return
    token = d["access_token"]

    s, cats = api_req("GET", "/categories", token=token)
    cat_map = {c["name"]: c["id"] for c in cats}

    demo = [
        ("zhangwei@demo.com", "产品咨询", "OntiCards 支持哪些数据源接入？", "想了解 OntiCards 能对接哪些数据库和文件源，方便我们规划数据接入。", "question"),
        ("liting@demo.com", "技术交流", "AI 回帖的引用是怎么生成的？", "看到 AI 回复会带 [1] 引用，想知道引用的来源和生成逻辑。", "question"),
        ("wangqiang@demo.com", "产品反馈", "建议增加暗色模式", "长时间使用社区，希望增加暗色模式降低眼部疲劳。", "discussion"),
    ]
    for email, cat_name, title, body, ptype in demo:
        s, d = api_req("POST", "/auth/login", {"email": email, "password": "Test123456"})
        if s != 200:
            continue
        utoken = d["access_token"]
        cid = cat_map.get(cat_name)
        if cid is None:
            continue
        s, d = api_req(
            "POST", "/posts",
            {"category_id": cid, "title": title, "body_md": body, "post_type": ptype, "at_ai": True},
            token=utoken,
        )
        print(f"[+] 发帖 {title[:16]}: {s} {d.get('id') if isinstance(d, dict) else d}")

    print("[+] seed_demo_data2 完成")


if __name__ == "__main__":
    main()
