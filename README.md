# README.md

项目：多模态医疗辅助问诊系统（RAG + 国内大模型 API 企业版）

## 多模态医疗辅助问诊系统

基于 RAG + 国内合规大模型 API 构建的药品科普辅助问诊平台。

⚠️ 重要免责声明：本系统仅作为药品知识科普工具，不能替代执业医师诊断，不可用于开具处方；任何身体不适请前往正规医疗机构就诊。

### 项目简介

本系统结合 RAG 检索增强生成、多模态图像解析能力，用户可以输入文字症状描述、上传检验报告 / 患处图片。系统在内网药品说明书知识库检索相关资料，调用国内大模型 API 生成药品科普回答。

- 原始问诊文件、用户记录内网私有化存储
- 调用外部大模型前自动隐私脱敏，规避隐私泄露、数据出境风险
- 支持 RBAC 多角色权限管理、知识库文档管理、用量监控审计

### 容量与规模预期

- 注册用户约 3000 人，日活约 300，峰值 QPS < 50
- 单台 4C8G 服务器即可承载，不引入 Kubernetes，Docker Compose 统一编排

### 技术栈

- 后端：Python3.12、FastAPI、Celery、Redis
- 数据库：MySQL8.0、Qdrant 向量库
- RAG：bge-large-zh、bge-reranker-large、BM25 + 向量混合检索
- 前端：Vue3 + Element Plus
- 部署：Docker Compose，可观测：OpenTelemetry、Prometheus

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

5. 访问前端页面：`http://127.0.0.1:8080`
6. API 接口地址：`http://127.0.0.1:8000/api/v1`

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
