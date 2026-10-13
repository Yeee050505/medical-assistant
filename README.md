# 多模态医疗辅助问诊系统

[![CI](https://github.com/Yeee050505/medical-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/Yeee050505/medical-assistant/actions/workflows/ci.yml)

项目：RAG + 国内大模型 API 企业版

基于 RAG + 国内合规大模型 API 构建的药品科普辅助问诊平台。

⚠️ 重要免责声明：本系统仅作为药品知识科普工具，不能替代执业医师诊断，不可用于开具处方；任何身体不适请前往正规医疗机构就诊。

### 项目简介

本系统结合 RAG 检索增强生成、多模态图像解析能力，用户可以输入文字症状描述、上传检验报告 / 患处图片。系统在内网药品说明书知识库检索相关资料，调用国内大模型 API 生成药品科普回答。

- 原始问诊文件、用户记录内网私有化存储
- 调用外部大模型前自动隐私脱敏，规避隐私泄露、数据出境风险
- 支持 RBAC 多角色权限管理、知识库文档管理、用量监控审计

### 容量与规模预期

- 注册用户约 3000 人，日活约 300，峰值 QPS < 50
- 单台 4C8G 服务器即可承载，不引入 Kubernetes，MySQL / Redis / Qdrant 本机服务常驻部署

### 技术栈

- 后端：Python3.12、FastAPI、Celery（RAG 异步入库）、Redis
- 数据库：MySQL8.0、Qdrant 向量库
- RAG：BM25 + 向量混合检索（RRF 融合）、embedding Provider 可切换（mock / OpenAI 兼容 API）
- 前端：Vue3 + Element Plus（SSE 流式渲染）
- 部署：Nginx 反代 + uvicorn / Celery worker，可观测：用量统计 + 审计日志 + Prometheus

### 环境依赖

后端 Python 依赖（Python 3.12，conda 环境 `medical`）：

```
fastapi
uvicorn
celery
redis
pymysql
qdrant-client
pdfplumber
paddleocr
sentence-transformers
rank_bm25
```

基础中间件：

```
MySQL >= 8.0（本机服务，3306；执行 docker/mysql/init.sql 初始化建表）
Redis 5.0+（本机 Windows 服务，D:\redis，6379，无密码）
Qdrant >= 1.19（本机 D:\qdrant，6333，Windows 原生单文件，无容器）
```

本机开发运行方式：

- Python 业务服务：`conda activate medical` 后本机裸跑（uvicorn / celery）
- MySQL、Redis、Qdrant：本机服务常驻（Windows 服务 `Redis`、Qdrant 进程 `D:\qdrant\qdrant.exe`）
- 前端：`npm run dev` 本机运行
- 生产/演示：同上，业务服务打包为进程/服务运行

### 项目目录结构

```
project-root/
├── backend/               # FastAPI业务服务（含网关中间件）
│   ├── api/               # 接口路由
│   ├── core/              # 鉴权、限流、traceId、配置
│   ├── rag/               # RAG核心模块
│   ├── llm_proxy/         # 大模型代理、脱敏、熔断SDK
│   ├── tasks/             # Celery异步任务
│   ├── models/            # 数据库模型
│   └── utils/             # 工具类、脱敏、trace工具
├── frontend/              # Vue前端代码
├── docs/                  # 项目文档 API / architecture / db / tech-stack
├── docker/                # MySQL初始化脚本
├── tests/                 # pytest 用例
└── README.md              # 项目说明文档
```

### 快速启动

1. 克隆项目代码
2. 复制 `.env.example` 为 `.env`，修改配置（大模型 API 密钥、数据库账号）
3. 启动本机服务：MySQL、Redis（Windows 服务 `Redis`）、Qdrant：

```bash
D:\qdrant\qdrant.exe
```

4. 初始化 Python 环境并启动后端：

```bash
conda create -n medical python=3.12 -y
conda activate medical
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --port 8000
```

5. 启动前端（另开终端）：

```bash
cd frontend
npm install
npm run dev
```

6. 可选：启用 Celery 异步入库（`.env` 设 `RAG_INGEST_ASYNC=true` 后启动 worker）：

```bash
# 工作目录 backend/（或任意目录 + PYTHONPATH 指向 backend）
celery -A app.core.celery_app:celery_app worker --pool=solo -l info
```

7. 访问前端页面：`http://localhost:8080`，API 地址：`http://127.0.0.1:8000/api/v1`

### 测试

```bash
# 后端（需 MySQL / Redis / Qdrant 本机服务 + init.sql 已执行）
pytest tests -q --cov=app --cov-report=term   # 44 个用例，覆盖率先 84%，CI 门禁 75%
ruff check backend tests scripts

# RAG 检索质量评估（内置 12 条标注用例，输出 recall@5 报告）
python scripts/rag_eval.py --write            # 报告写入 docs/rag-eval.md

# 前端构建验证
cd frontend && npm run build
```

每次 push 自动执行 GitHub Actions CI（后端 ruff + pytest 覆盖率门禁 ≥75%、前端 vite build，含 MySQL/Redis/Qdrant 服务容器）。

CI 中的 `tests/test_rag_eval.py` 是检索质量门禁：样例用例 hybrid recall@5 < 0.8 即失败，防止检索退化。

### 数据库迁移（Alembic）

新环境初始化二选一：

```bash
# 方式一：种子脚本（建表 + admin 账号，CI 采用此方式）
mysql -u medical -p medical < docker/mysql/init.sql

# 方式二：Alembic 迁移（仅建表；已有表时幂等跳过）
cd backend && alembic upgrade head

# 后续 schema 变更：改 models → autogenerate → review → upgrade
alembic revision --autogenerate -m "add column"
alembic upgrade head
```

### 性能压测

Locust 混合场景（50 并发 × 60s：问诊对话 / 知识库检索 / 健康检查 / 用户信息，mock LLM）：

| 指标 | 结果 |
|---|---|
| 总请求 / 失败 | 3896 / **0** |
| 吞吐 | **65.7 RPS**（设计目标峰值 <50 满足） |
| 延迟 P50 / P95 / P99 | **40ms / 560ms / 610ms** |
| 分端点 P50 | chat 消息 520ms（含 mock 流式生成）、检索 12ms、健康检查 22ms |

```bash
# 复现（压测期间临时放大限流阈值：RATE_LIMIT_QPS=1000000）
locust -f locustfile.py --headless -u 50 -r 10 -t 60s --csv=docs/benchmark/locust --host http://127.0.0.1:8000
```

原始结果见 `docs/benchmark/locust_*.csv`。

### 可观测性

- **结构化 JSON 日志**：每行含 `traceId`（contextvar 贯穿，跨异步任务隔离），`LOG_JSON=false` 切回文本格式
- **全链路 traceId**：请求入口生成/透传，响应头 `X-Trace-Id`、`X-Cost-Ms`，同步落 `audit_log` 表（`GET /monitor/log` 可按 traceId 检索）
- **Prometheus 指标**：`GET /api/v1/monitor/metrics`（admin token），暴露 `http_requests_total`、`http_request_duration_seconds`、`llm_calls_total`、`llm_tokens_total`、`rag_queries_total`、`cache_ops_total` 等
- **用量与审计**：`GET /monitor/llm/cost` 按 api_type 聚合 token 与费用

### 限流与缓存

- **滑动窗口限流**：Redis ZSET 实现（消除固定窗口临界突刺），按登录用户 / 客户端 IP 维度，默认 10 QPS，超限 429；Redis 不可用时降级放行
- **两级缓存**：embedding 结果缓存（7 天，内容不可变）+ RAG 检索结果缓存（60s TTL）；知识库入库/启停时同步失效（BM25 索引 + 结果缓存）

### 部署教程

开发环境部署：

- 本机服务常驻 + `uvicorn` 直跑业务服务，适合开发调试。

生产环境部署（用户规模约 3000）：

- 打包 FastAPI 服务进程（Nginx 反代 + uvicorn）
- 本机服务常驻：MySQL、Redis、Qdrant 单实例，每日快照备份
- Nginx 反向代理统一入口，配置 HTTPS 与前端静态资源托管
- 配置 Prometheus + Grafana 监控、链路追踪、日志收集
- 配置出站白名单，仅允许访问国内大模型服务商 API 地址
- 配置告警：API 调用失败、token 用量超额告警

### 注意事项

- 隐私安全：上传图片、问诊记录存储在内网，调用外部大模型接口会自动脱敏，清除身份证、手机号等敏感信息。
- 大模型幻觉控制：回答强制引用 RAG 检索到的文档片段，禁止编造药品信息，回答末尾追加免责声明。
- API 密钥管理：大模型 API 密钥存放于环境变量，禁止硬编码在代码中，禁止提交到代码仓库。
- 限流保护：接入层配置 QPS 限流，防止短时间大量请求造成 API 费用暴增。
- 合规约束：系统严禁输出疾病诊断、处方、治疗方案，输出内容仅作科普参考。

### 许可证

本项目仅用于学习与毕业设计演示，禁止直接上线用于正式医疗业务场景。
