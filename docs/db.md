# 数据库设计（db.md）

项目：多模态医疗辅助问诊系统（RAG + 国内大模型 API 企业版）

文档版本：V1.0

- 关系型数据库：MySQL 8.0（复用本机 3306 实例），库名 `medical`，字符集 `utf8mb4`
- 向量数据库：Qdrant 1.19（本机 6333），collection 设计见文末
- 建表语句：`docker/mysql/init.sql`，使用 medical 账号执行：`mysql -umedical -p medical < docker/mysql/init.sql`

## 1 sys_user 用户表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK AUTO_INCREMENT | 用户 ID |
| username | VARCHAR(64) UNIQUE | 登录名 |
| password_hash | VARCHAR(255) | bcrypt 密码散列 |
| role | VARCHAR(16) | `admin` / `staff` |
| status | TINYINT | 1 启用 0 禁用 |
| created_at / updated_at | DATETIME | 创建 / 更新时间 |

索引：`uk_username(username)`

## 2 chat_session 问诊会话表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK AUTO_INCREMENT | 自增主键 |
| session_id | VARCHAR(32) UNIQUE | 对外会话 ID（sess- 前缀 uuid） |
| user_id | BIGINT | 归属用户，关联 sys_user.id |
| summary | VARCHAR(255) | 对话摘要（首轮问题截断） |
| status | VARCHAR(16) | `active` / `closed` |
| created_at / updated_at | DATETIME | 创建 / 最后活跃时间 |

索引：`uk_session_id(session_id)`、`idx_user_id(user_id, created_at)`

## 3 chat_message 问诊消息表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK AUTO_INCREMENT | 自增主键 |
| session_id | BIGINT | 关联 chat_session.id |
| role | VARCHAR(16) | `user` / `assistant` |
| content | MEDIUMTEXT | 消息内容（AI 回答含免责声明） |
| reference_docs | JSON NULL | 召回文档片段数组 `[{docId, drugName, chunkContent}]` |
| trace_id | VARCHAR(64) | 全链路追踪 ID |
| created_at | DATETIME | 发送时间 |

索引：`idx_session_id(session_id, id)`、`idx_trace_id(trace_id)`

## 4 rag_doc 知识库文档表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK AUTO_INCREMENT | 自增主键 |
| doc_id | VARCHAR(32) UNIQUE | 对外文档 ID（doc 前缀 uuid） |
| drug_name | VARCHAR(128) | 药品名称 |
| version | VARCHAR(32) | 说明书版本号 |
| file_path | VARCHAR(255) | PDF 内网存储路径 |
| status | VARCHAR(16) | `processing` / `success` / `failed` |
| enabled | TINYINT | 1 启用参与检索 0 下线 |
| error_msg | VARCHAR(512) | 入库失败原因 |
| uploader_id | BIGINT | 上传管理员 ID |
| created_at / updated_at | DATETIME | 上传 / 更新时间 |

索引：`uk_doc_id(doc_id)`、`idx_drug_name(drug_name)`、`idx_status(status)`

## 5 task_record 异步任务表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK AUTO_INCREMENT | 自增主键 |
| task_id | VARCHAR(64) UNIQUE | Celery task id |
| doc_id | VARCHAR(32) | 关联 rag_doc.doc_id |
| type | VARCHAR(32) | `doc_ingest` / `usage_stat` / `vector_snapshot` |
| status | VARCHAR(16) | `processing` / `success` / `failed` |
| error_msg | VARCHAR(512) | 失败原因 |
| created_at / updated_at | DATETIME | 创建 / 更新时间 |

索引：`uk_task_id(task_id)`、`idx_doc_id(doc_id)`

## 6 llm_usage 大模型用量表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK AUTO_INCREMENT | 自增主键 |
| trace_id | VARCHAR(64) | 链路 ID |
| user_id | BIGINT | 触发用户 |
| provider | VARCHAR(32) | 服务商（mock / deepseek / qwen ...） |
| model | VARCHAR(64) | 模型名 |
| api_type | VARCHAR(16) | `llm` / `vl` |
| prompt_tokens | INT | 输入 token 数 |
| completion_tokens | INT | 输出 token 数 |
| cost | DECIMAL(10,6) | 预估费用（元） |
| duration_ms | INT | 调用耗时 |
| status | VARCHAR(16) | `success` / `failed` |
| created_at | DATETIME | 调用时间 |

索引：`idx_created_at(created_at)`、`idx_trace_id(trace_id)`、`idx_user_id(user_id)`

## 7 audit_log 审计日志表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK AUTO_INCREMENT | 自增主键 |
| trace_id | VARCHAR(64) | 链路 ID |
| user_id | BIGINT NULL | 未登录接口为 NULL |
| method | VARCHAR(8) | GET / POST ... |
| path | VARCHAR(255) | 请求路径 |
| code | INT | 返回状态码 |
| ip | VARCHAR(45) | 客户端 IP |
| cost_ms | INT | 处理耗时 |
| created_at | DATETIME | 访问时间 |

索引：`idx_trace_id(trace_id)`、`idx_created_at(created_at)`

## 8 file_object 文件表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BIGINT PK AUTO_INCREMENT | 自增主键 |
| file_id | VARCHAR(32) UNIQUE | 对外文件 ID（file 前缀 uuid） |
| user_id | BIGINT | 上传者 |
| file_path | VARCHAR(255) | 内网存储路径 |
| mime | VARCHAR(64) | 文件类型 |
| size_bytes | BIGINT | 文件大小 |
| biz_type | VARCHAR(16) | `chat` 问诊图片 / `rag` 药品 PDF |
| created_at | DATETIME | 上传时间 |

索引：`uk_file_id(file_id)`、`idx_user_id(user_id)`

## 9 RBAC 权限模型

角色固定为 `admin` / `staff`，权限标识映射写在后端配置（规模 3000 用户，无需权限表）：

| 角色 | 权限标识 |
| --- | --- |
| admin | `rag:read` `rag:write` `user:manage` `chat:read` `monitor:admin` |
| staff | `chat:read`（仅本人数据） |

## 10 Qdrant Collection 设计

Collection 名：`drug_chunks`

向量配置：稠密向量 `dense`，bge-large-zh 输出，维度 1024，Cosine 距离，HNSW 索引。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | 点 ID（uint64） | 切片自增 ID |
| vector.dense | FLOAT_VECTOR(1024) | bge-large-zh 向量 |
| payload.doc_id | keyword 索引 | 来源文档，关联 rag_doc |
| payload.drug_name | keyword 索引 | 药品名，标量过滤用 |
| payload.section | keyword 索引 | 章节名（用法用量 / 禁忌 / 不良反应 ...） |
| payload.chunk_text | text | 原文切片 |

检索流程：Qdrant 向量召回 TopK=40（filter: 文档 enabled=true）→ BM25 关键词召回 TopK=40 → RRF 融合 → bge-reranker 重排 → TopN=5。
