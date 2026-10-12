# tech-stack.md

项目：多模态医疗辅助问诊系统（RAG + 国内大模型 API 企业版）

文档版本：V1.1

## 容量设计预期

- 注册用户规模：约 3000 人，日活约 300，峰值 QPS < 50
- 部署目标：单台 4C8G 服务器即可承载（向量/重排模型与业务服务可分机部署）
- 不引入 Kubernetes，统一使用 Docker Compose 编排

## 整体技术栈

### 后端核心

- 开发语言：Python 3.12（conda 环境 `medical`，本机裸跑业务服务）
- Web 框架：FastAPI（业务服务 + 网关层：JWT 鉴权、限流、traceId 中间件）；Nginx（生产反代）
- 异步任务：Celery + Redis（任务队列、任务状态存储）
- 权限鉴权：JWT + RBAC 角色权限控制（FastAPI 中间件与依赖统一处理）

### 数据库 & 向量库

- 关系型数据库：MySQL 8.0（用户、会话、日志、文档元信息）
- 向量数据库：Qdrant（存储文档向量，用于 RAG 检索）
- 缓存：Redis（接口限流、会话缓存、Celery broker、token 黑名单）

### RAG 检索模块

- 文本向量化模型：bge-large-zh
- 重排模型：bge-reranker-large
- 检索策略：BM25 关键词检索 + 向量检索，RRF 融合打分
- 文档处理：PyPDF2、pdfplumber、PaddleOCR（PDF/OCR 解析清洗、语义切片）

### 大模型能力（调用 API，本地不部署基座）

- 多模态 VL API：国内合规服务商多模态接口，图片解析提取文本
- 文本 LLM API：国内大模型文本生成接口，生成回答（支持流式输出）
- 内部 SDK 封装：增加重试、熔断、多服务商切换、隐私脱敏逻辑
- 开发阶段：LLM/VL 调用走 mock 实现（统一 Provider 接口），填入真实 API Key 后配置开关切换，业务代码不感知

### 前端

- 前端框架：Vue3 + Element Plus
- 网络请求：Axios
- 流式渲染：SSE（EventSource / axios 流式读取），用于问诊回答边收边显

### 部署 & 运维 & 可观测

- 部署形态：全本机进程、零容器；MySQL 3306、Redis 6379、Qdrant 6333 均为本机服务
- 反向代理：Nginx
- 链路追踪：OpenTelemetry，TraceId 全链路埋点
- 日志：Loki 单实例收集审计（复用 Grafana 查询，不部署整套 ELK）
- 监控：Prometheus + Grafana（服务指标、LLM token 用量监控、告警）

## 项目架构分层

1. 接入层：Nginx（生产反代 / HTTPS）+ FastAPI 网关中间件（鉴权、限流、traceId、日志埋点）
2. 应用服务层：FastAPI，业务逻辑、RAG、会话管理、调用 LLM API
3. 任务队列层：Celery，异步文档解析、向量化入库
4. 存储层：MySQL、Redis、Qdrant、本地文件存储
5. 外部服务层：调用国内大模型服务商 API（VL + LLM）

## 开发 / 测试工具

- 代码管理：Git + Gitea/GitHub
- 接口测试：Postman / Apifox
- 单元测试：pytest
- 代码规范：ruff、black
