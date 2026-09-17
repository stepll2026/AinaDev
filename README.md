# AI 原生开发者社区（ai-native-community）

面向企业的 **AI 原生开发者社区**：发帖、回帖、知识库问答由 **LangGraph Agent 流水线** 自动运维（合规审查 → 意图路由 → RAG 检索 → 证据判定 → AI 生成回复），并内置 **MCP 服务**，可接入豆包工作等智能体生态做每日运维。

- 前端：Next.js 15（App Router）+ TypeScript + Tailwind
- 后端：FastAPI + SQLAlchemy(async) + LangGraph 流水线 + ARQ 定时任务
- 向量检索：pgvector / JSONB+余弦（自动降级），中文全文检索 zhparser / ILIKE（自动降级）
- 部署：Docker Compose（4 容器），依赖云端 PostgreSQL / Redis

---

## 一、功能总览

| 模块 | 说明 |
|---|---|
| 社区论坛 | 多栏目、发帖/回帖/点赞/收藏/搜索/引用回复/置顶/精华/锁帖/问答已解决 |
| AI 原生运维 | 发帖自动进入 Agent 流水线：合规审查 → 路由 → RAG 检索 → 证据判定 → AI 回帖 |
| 无证据不回复 | Judge 节点相似度低于栏目阈值（默认 0.7）绝不回帖，转人工或明确告知 |
| 全链路审计 | 每个 Agent 决策写入 `agent_runs`，后台可视化查看（含 prompt/响应/耗时/评分） |
| 知识库 RAG | 上传 PDF / DOCX / MD / TXT / URL 自动解析切片向量化，混合检索（向量+全文） |
| 合规审查 | LLM 审查 + 内置风险词表双保险，high 自动隐藏、mid 进人工队列 |
| 人工审核 | 待审队列、举报处理、审核操作（通过/隐藏/删除/警告/驳回）全部留痕 |
| 多角色账号 | human（普通用户）/ agent（AI 管理员，不可登录）/ system（系统账号） |
| 附件上传 | 发帖/回帖支持图片、文档、压缩包；格式与大小限制后台可调 |
| 模型配置 | 后台可视化配置 OpenAI 兼容协议模型（通义/火山/DeepSeek/自建 vLLM），Key AES 加密存储 |
| 邀请码注册 | 管理员生成邀请码，新用户凭码注册，有效期可配 |
| 资讯与周报 | ARQ 定时任务：每日资讯抓取、每周运维周报、48h 无回复提醒、重复帖检测、僵尸帖归档 |
| MCP Server | 15 个运维工具（合规审查/知识库/帖子/栏目/审核/资讯/周报/统计），HTTP Streamable 协议 |

---

## 二、系统架构

```
                        ┌─────────────────────────────────────────────┐
   浏览器 / 豆包工作     │  Docker Compose（单机 4 容器）               │
   (MCP 客户端)         │                                             │
        │               │  ┌─────────┐   /api/    ┌──────────────┐   │
        │  http(s)      │  │  nginx  │───────────▶│  api(FastAPI)│   │
        └───────────────┼─▶│  8090:80│   /mcp     │  :8000       │   │
                        │  │         │───────────▶│  ┌──────────┐│   │
                        │  └────┬────┘   /        │  │ MCP 服务 ││   │
                        │       │                │  └──────────┘│   │
                        │       │                └──────┬───────┘   │
                        │       │                       │ 事件      │
                        │  ┌────▼────┐              ┌───▼────────┐  │
                        │  │  web    │              │ worker(ARQ)│  │
                        │  │Next.js  │              │ :8000      │  │
                        │  │ :3000   │              └─────┬──────┘  │
                        │  └─────────┘                    │         │
                        └────────────────────────────────┼─────────┘
                                                         │
                          ┌──────────────────────────────┼──────────────┐
                          │ 外部依赖（云端，部署时提供）   ▼              │
                          │  ┌──────────────┐   ┌────────────────────┐  │
                          │  │ PostgreSQL   │   │ Redis（ARQ 队列/   │  │
                          │  │ (业务数据/    │   │  定时任务/缓存)     │  │
                          │  │  pgvector)   │   └────────────────────┘  │
                          │  └──────────────┘                           │
                          └─────────────────────────────────────────────┘
```

**容器清单**

| 容器 | 镜像 | 端口 | 职责 |
|---|---|---|---|
| `community-nginx` | nginx:1.27-alpine | **8090 → 80**（对外） | 反代 web / api / mcp / uploads |
| `community-api` | 本地构建 | 8000（内网） | FastAPI：REST API + MCP Server |
| `community-web` | 本地构建 | 3000（内网） | Next.js 生产构建 |
| `community-worker` | 本地构建 | - | ARQ 异步任务 + 定时任务（消费流水线事件） |

---

## 三、技术栈

- **后端**：Python 3.12+ · FastAPI · SQLAlchemy 2 (async) · psycopg · LangGraph · fastmcp · ARQ · pydantic v2
- **前端**：Next.js 15 · React 19 · TypeScript · Tailwind CSS
- **数据**：PostgreSQL 14+（建议装 pgvector、zhparser 可选）· Redis 6+
- **LLM**：OpenAI 兼容协议（通义千问 DashScope / 火山方舟 / DeepSeek / OpenAI / 自建 vLLM / Ollama 均可）

---

## 四、部署前准备

1. **一台 Linux 服务器**（Ubuntu 22.04+ / Debian 12+ 推荐），已装 Docker 与 Docker Compose v2：

   ```bash
   docker --version          # 建议 24+
   docker compose version    # 建议 2.20+
   ```

2. **云端 PostgreSQL**：创建数据库与账号，记录连接串。
   建议开启 `pgvector` 扩展（可选；未开启自动降级为 JSONB+余弦检索）：

   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE EXTENSION IF NOT EXISTS zhparser;  -- 可选，中文全文检索
   ```

3. **云端 Redis**：创建实例，记录地址与密码（用于 ARQ 任务队列）。

4. **LLM API Key**：任选 OpenAI 兼容服务商（推荐通义千问 / 火山方舟）。部署后通过后台「模型配置」页配置，**不会写入代码或明文存储**。

5. **安全组放行端口**：对外访问端口（默认 **8090**）需在云安全组放行。若 80 端口空闲，可改为 80。

---

## 五、快速部署（生产）

### 第 1 步：获取代码

```bash
git clone https://github.com/stepll2026/AinaDev.git ai-native-community
cd ai-native-community
```

### 第 2 步：配置环境变量

```bash
cp .env.example .env
vim .env   # 按下方表格填写
```

**必填项**：

| 变量 | 说明 | 示例 |
|---|---|---|
| `PUBLIC_BASE_URL` | 公网访问地址（MCP 与通知链接使用） | `http://192.168.1.100:8090` |
| `DATABASE_URL` | PostgreSQL 异步连接串 | `postgresql+psycopg://user:pass@<db-host>:5432/community` |
| `REDIS_URL` | Redis 连接串 | `redis://:pass@<redis-host>:6379/0` |
| `JWT_SECRET` | 随机 32 字节 hex：`openssl rand -hex 32` | |
| `AES_KEY` | AES-256 密钥（32 字节 hex）：`openssl rand -hex 32`，用于加密模型 API Key | |
| `MCP_API_KEY` | MCP 访问令牌（豆包工作配置时填 Bearer） | |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 初始超管（首次启动自动创建） | |

**可选项**：`SITE_NAME`、`SITE_DESCRIPTION`、`INVITE_EXPIRE_DAYS`、`SMTP_*`（邮件通知）、`DEFAULT_LLM_*`（默认模型，首次启动写入库，之后后台可改）。

### 第 3 步：启动

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

- 首次启动自动建表 + 写入默认栏目与种子数据
- 若 80 端口被占用，编辑 `docker-compose.prod.yml`，把 `8090:80` 改成其他端口（如 `8080:80`），并同步修改 `.env` 的 `PUBLIC_BASE_URL`

### 第 4 步：验证

```bash
curl http://<服务器IP>:8090/api/health
# {"status":"ok","site":"AI 开发者社区","mcp_endpoint":"http://<IP>:8090/mcp"}
```

浏览器打开 `http://<服务器IP>:8090`，用 `ADMIN_EMAIL/ADMIN_PASSWORD` 登录（首次登录后建议立即修改密码）。

---

## 六、初始化配置（上线必做）

登录超管后，按顺序完成：

1. **「模型配置」页签** → 点击「+ 新建模型配置」→ 选模板「通义千问 DashScope」→ 填入 API Key → 保存 → 点「测试连接」确认 `OK` → 设为默认。AI 回帖与知识库向量化均使用默认配置。
2. **「栏目 & AI 管理员」页签** → 为各栏目配置 AI 管理员（persona 名称、系统提示词、所属模型、回帖阈值）→ 确认「自动回帖」开启。
3. **「知识库」页签** → 选择栏目 → 上传产品文档 / FAQ / 运维手册（PDF、DOCX、MD、TXT）或添加网页 URL。等待状态变为 `ready`。
4. **「审核 / 资讯 / 用户」页签** → 生成邀请码分发给员工注册。
5. **「审计 & 设置」页签** → 核对站点名称、MCP 令牌、附件上传限制（允许格式、单文件大小）。

> 知识库文档上传后自动切片向量化；更换 embedding 模型后请在知识库列表点「重建」重新向量化。

---

## 七、AI 原生流水线

发帖 / 回帖事件触发流水线（LangGraph 拓扑，worker 异步执行，全决策落 `agent_runs`）：

```
① Guardrail 合规审查（LLM + 风险词表双保险）
    └─ high → 自动隐藏 + 通知人类管理员
    └─ mid  → 进入人工审核队列
    └─ low  → 继续
② Route 路由（栏目自动回帖开关 + AI 管理员是否存在 + 是否 @AI）
③ Retrieve RAG 混合检索（仅本栏目知识库命名空间，向量 + 全文）
④ Judge 证据判定（top1 相似度 < 栏目阈值 0.7 → 无证据不回帖，通知补文档）
⑤ Generate 生成回复（硬约束：只使用证据回答，末尾 [1][2] 标注来源；证据不足只输出 NO_ANSWER）
⑥ Postprocess 后处理（LLM 自检置信度 < 0.6 → 转人工复核；自动打标签；重复帖检测；通知订阅者）
```

**阈值可配置**：栏目级 `reply_threshold`（回帖相似度阈值）、AI 管理员级 `self_review_threshold`（自检置信度），后台均可调整。

---

## 八、MCP 服务接入（豆包工作 / 任意 MCP 客户端）

1. 登录超管 → 「总览 / MCP」页签 → 复制 **MCP 接入信息**：URL 与 Authorization 令牌。
2. 在豆包工作中添加 MCP 服务器：
   - **URL**：`http://<服务器IP>:8090/mcp`（注意尾部 `/`）
   - **传输**：HTTP（Streamable）
   - **Headers**：`Authorization: Bearer <MCP_API_KEY>`
3. 连接成功后可调用 15 个工具：合规审查、知识库检索、帖子/栏目管理、审核处置、用户/邀请码、每日资讯、周报生成、系统统计等，实现每日自动化运维。

---

## 九、运维与升级

**常用命令**

```bash
docker compose -f docker-compose.prod.yml ps            # 状态
docker compose -f docker-compose.prod.yml logs -f api   # 后端日志
docker compose -f docker-compose.prod.yml logs -f worker # 任务日志
docker compose -f docker-compose.prod.yml restart api   # 重启
```

**升级**

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

**数据备份**：备份 PostgreSQL（`pg_dump`）与 Redis；上传文件在 `uploads` 卷（`docker volume ls` 查看 `ai-native-community_uploads`）。

---

## 十、常见问题

| 问题 | 处理 |
|---|---|
| 外网访问超时 | 云安全组放行对外端口（默认 8090） |
| 80 端口被占用 | 修改 compose 端口映射与 `PUBLIC_BASE_URL` |
| AI 不回复 | ① 模型配置是否已填 Key 并设为默认 ② 栏目是否配置 AI 管理员并开启自动回帖 ③ 知识库是否有相关证据（检索阈值）④ 查看「Agent 执行记录」定位 |
| 知识库文档 failed | 查看错误信息；模型 Key 是否正确；文档是否可解析；换模型后记得「重建」 |
| 更换模型 | 后台「模型配置」新增/编辑并测试连接 → 设为默认 → 知识库「重建」索引 |
| 中文全文检索不生效 | 数据库未装 zhparser 时自动降级为 ILIKE，不影响功能 |
| 修改 MCP 令牌 | 后台「审计 & 设置」修改后，同步更新豆包工作中的配置 |

---

## 十一、本地开发

```bash
# 后端（Python 3.12+）
cd apps/api
python -m venv .venv && .venv\Scripts\activate   # Windows；Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 配置数据库 / Redis
python run.py          # http://localhost:8000

# 前端
cd apps/web
npm install
npm run dev            # http://localhost:3000

# 本地起数据库（可选）：docker compose up -d db redis
```

> Windows 注意：项目已内置 SelectorEventLoop 适配，解决 psycopg async 与 Proactor 的兼容问题。

---

## 十二、目录结构

```
├── apps/
│   ├── api/                    # FastAPI 后端
│   │   ├── app/
│   │   │   ├── api/            # REST 路由（auth/posts/categories/admin_*/uploads…）
│   │   │   ├── agent/          # LangGraph 流水线（runner + nodes）
│   │   │   ├── models/         # SQLAlchemy 模型（users/posts/categories/rag/agent/system）
│   │   │   ├── schemas/        # Pydantic 模型
│   │   │   ├── services/       # LLM/RAG/合规/审计/通知/运维/资讯/文档/后处理
│   │   │   ├── tasks/          # ARQ worker + 定时任务
│   │   │   └── mcp/            # MCP Server（15 工具）
│   │   ├── run.py              # 启动入口（含 Windows 事件循环适配）
│   │   └── requirements.txt
│   └── web/                    # Next.js 15 前端
│       ├── app/                # 页面路由（首页/发帖/帖子/栏目/搜索/个人/后台）
│       ├── components/         # 组件（含管理后台各面板）
│       └── lib/                # API 客户端 / 鉴权
├── docker/
│   ├── nginx/nginx.conf        # 反代 /api /mcp /uploads
│   └── postgres/               # 本地开发数据库初始化
├── docker-compose.yml          # 本地开发（内置 db/redis）
├── docker-compose.prod.yml     # 生产（外部云端 PG/Redis）
├── .env.example                # 环境变量模板（脱敏）
└── README.md
```