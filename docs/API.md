# API.md

项目：多模态医疗辅助问诊系统（RAG + 国内大模型 API 企业版）

文档版本：V1.1

协议：HTTP/HTTPS

Content-Type：JSON（文件上传接口使用 multipart/form-data）

鉴权方式：请求头 `Authorization: Bearer {JWT_TOKEN}`

网关：Nginx 反代 + FastAPI 网关中间件（JWT 鉴权 / 限流 / traceId），接口统一前缀：`/api/v1`

重要说明：

- 药品知识库、问诊原始数据全部内网存储；调用外部大模型 API 前自动执行隐私脱敏。
- AI 生成回答强制追加医疗免责声明，系统输出内容仅作药品科普，不可替代执业医师诊断，不可作为处方依据。
- 所有接口统一返回标准 JSON 结构体；业务异常携带错误码与提示信息，便于前端统一处理。
- 问诊类接口为长耗时接口（VL 解析 + RAG 检索 + LLM 生成），反代对 `/chat/**` 路径读超时放宽至 60s；多轮消息接口采用 SSE 流式返回，避免前端超时。

## 通用返回结构体

```json
{
  "code": 200,
  "msg": "success",
  "data": {},
  "traceId": "uuid-xxxx"
}
```

## 全局状态码约定

| 状态码 | 含义 |
| --- | --- |
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未登录 / JWT 令牌过期 |
| 403 | RBAC 权限校验不通过，禁止访问 |
| 404 | 资源不存在 |
| 429 | 请求触发限流 |
| 500 | 服务内部异常 |

## 一、用户与权限模块（RBAC + JWT）

### 1.1 用户登录

- Path：`POST /api/v1/auth/login`
- 鉴权：无需鉴权

Request Body：

```json
{
  "username": "admin",
  "password": "xxx"
}
```

Response data：

```json
{
  "token": "jwt-token-string",
  "refreshToken": "refresh-token-string",
  "expireIn": 7200,
  "role": "admin",
  "userId": 1
}
```

### 1.2 获取当前登录用户信息

- Path：`GET /api/v1/auth/info`
- Header：`Authorization: Bearer {token}`

Response data：

```json
{
  "userId": 1,
  "username": "admin",
  "role": "admin",
  "permissions": ["rag:read", "rag:write", "user:manage", "chat:read"]
}
```

### 1.3 刷新令牌

- Path：`POST /api/v1/auth/refresh`
- 鉴权：无需 Bearer，Body 携带 refreshToken

Request Body：

```json
{
  "refreshToken": "refresh-token-string"
}
```

Response data：与 1.1 登录返回一致，签发新 token 对。

### 1.4 登出

- Path：`POST /api/v1/auth/logout`
- Header：`Authorization: Bearer {token}`

行为：将当前 token 写入 Redis 黑名单（有效期至自然过期），前端清除本地缓存。

Response data：

```json
{
  "success": true
}
```

### 1.5 用户列表查询（仅管理员）

- Path：`GET /api/v1/user/list`
- Query 参数：`page`（页码）、`size`（每页条数）、`keyword`（用户名关键词）
- Header：`Authorization: Bearer {token}`
- 权限标识：`user:manage`

### 1.6 创建用户（仅管理员）

- Path：`POST /api/v1/user/create`
- Header：`Authorization: Bearer {token}`
- 权限标识：`user:manage`

Request Body：

```json
{
  "username": "user01",
  "password": "xxx",
  "role": "staff"
}
```

## 二、多模态问诊核心模块

### 2.1 创建问诊会话（发起首轮问诊）

- Path：`POST /api/v1/chat/session/create`
- Header：`Authorization: Bearer {token}`

Request Body：

```json
{
  "userDesc": "嗓子干痒，轻微咳嗽",
  "imageList": ["file-uuid-1", "file-uuid-2"]
}
```

说明：`imageList` 先调用 2.3 文件上传接口获取 `fileId`，再传入；无图片时传空数组。

业务流程：

1. 后端调用 VL 多模态 API 解析图片，提取图片内结构化文本
2. 合并用户文字描述 + 图片解析文本，构造检索 Query，执行 RAG 混合检索
3. 调用文本 LLM API，结合召回药品说明书片段生成回答，自动追加免责声明
4. 保存会话与首轮问答记录到 MySQL

Response data：

```json
{
  "sessionId": "sess-xxxx",
  "answer": "【AI回答内容】\n提示：本内容仅为药品科普参考，不能替代执业医师诊断，不能作为处方依据，身体不适请前往医疗机构就诊。",
  "referenceDocs": [
    {
      "docId": "doc001",
      "drugName": "XXX感冒药",
      "chunkContent": "召回的说明书片段"
    }
  ]
}
```

### 2.2 发送会话消息（多轮追问，SSE 流式）

- Path：`POST /api/v1/chat/session/{sessionId}/message`
- Header：`Authorization: Bearer {token}`、`Accept: text/event-stream`
- 权限规则：普通用户仅可对自己的会话发消息

Request Body：

```json
{
  "userDesc": "那这个药饭前吃还是饭后吃？",
  "imageList": []
}
```

行为：在已有会话内追加一轮问答。复用 2.1 的 RAG + LLM 流程，回答以 SSE 增量下发，前端边收边渲染，避免长响应超时。

SSE 事件格式：

```
event: delta
data: {"content": "【增量文本片段】"}

event: done
data: {"sessionId": "sess-xxxx", "referenceDocs": [{"docId": "doc001", "drugName": "XXX感冒药", "chunkContent": "召回的说明书片段"}], "disclaimer": "本内容仅为药品科普参考，不能替代执业医师诊断，不能作为处方依据。"}

event: error
data: {"code": 50001, "msg": "大模型服务暂时繁忙，请稍后重试"}
```

降级说明：若客户端不支持 SSE（`Accept` 未包含 `text/event-stream`），则退化为普通 JSON 同步返回，结构同 2.1。

### 2.3 问诊图片文件上传

- Path：`POST /api/v1/file/upload`
- Content-Type：`multipart/form-data`
- Header：`Authorization: Bearer {token}`
- 参数：`file`（图片文件，支持 jpg/png/webp，单文件上限 10MB）

Response data：

```json
{
  "fileId": "file-uuid-1",
  "url": "内网访问地址，外部不可访问"
}
```

### 2.4 获取用户问诊会话列表

- Path：`GET /api/v1/chat/session/list`
- Query 参数：`page`、`size`
- Header：`Authorization: Bearer {token}`

返回会话列表，包含 `sessionId`、创建时间、对话摘要。

### 2.5 查询单条问诊会话详情

- Path：`GET /api/v1/chat/session/{sessionId}`
- Header：`Authorization: Bearer {token}`
- 权限规则：普通用户仅可查看自己的问诊记录；管理员可查看全部脱敏问诊记录

返回该会话全部历史消息（用户输入、AI 回答、引用文档、时间戳）。

## 三、RAG 药品知识库管理模块（管理员权限）

### 3.1 上传药品说明书 PDF 文档

- Path：`POST /api/v1/rag/doc/upload`
- Content-Type：`multipart/form-data`
- Header：`Authorization: Bearer {token}`
- 权限标识：`rag:write`
- 参数：`file`（PDF 文件）、`drugName`（药品名称）、`version`（文档版本号）

后台异步任务流程：OCR 识别 → 文本清洗 → 按章节语义切片 → 向量化入库（Celery 异步任务）

Response data：

```json
{
  "docId": "doc001",
  "taskId": "celery-task-uuid",
  "status": "processing"
}
```

### 3.2 查询文档入库异步任务状态

- Path：`GET /api/v1/rag/task/{taskId}`
- Header：`Authorization: Bearer {token}`

返回任务状态：`processing` / `success` / `failed`，失败时附带错误原因。

### 3.3 知识库文档列表

- Path：`GET /api/v1/rag/doc/list`
- Query 参数：`page`、`size`、`drugName`（药品名称检索关键词）
- Header：`Authorization: Bearer {token}`
- 权限标识：`rag:read`

返回字段：`docId`、药品名、版本、上传时间、启用状态。

### 3.4 文档启用 / 下线状态更新

- Path：`PUT /api/v1/rag/doc/status`
- Header：`Authorization: Bearer {token}`
- 权限标识：`rag:write`

Request Body：

```json
{
  "docId": "doc001",
  "status": "disable"
}
```

### 3.5 RAG 检索调试测试接口

- Path：`POST /api/v1/rag/search/test`
- Header：`Authorization: Bearer {token}`
- 权限标识：`rag:read`

Request Body：

```json
{
  "query": "阿莫西林的禁忌",
  "topK": 5
}
```

返回混合检索 + Rerank 重排后的召回片段，用于开发调试 RAG 检索效果。

## 四、系统监控、用量统计与运维接口

### 4.1 大模型 API 调用用量统计

- Path：`GET /api/v1/monitor/llm/cost`
- Query 参数：`startDate`、`endDate`
- Header：`Authorization: Bearer {token}`
- 权限标识：`admin`

返回内容：调用总次数、输入 token 总量、输出 token 总量、预估费用。

### 4.2 系统审计日志检索（脱敏）

- Path：`GET /api/v1/monitor/log`
- Query 参数：`traceId`、`startDate`、`endDate`
- Header：`Authorization: Bearer {token}`
- 权限标识：`admin`

### 4.3 服务健康探测接口

- Path：`GET /api/v1/health`
- 鉴权：无需鉴权

用于服务器存活探针 / 负载均衡健康检查，返回服务状态、外部大模型 API 连通性。

## 五、后台异步任务说明（Celery，无 HTTP 对外接口）

- 药品 PDF 文档批量解析、OCR 识别、文本切片、向量入库
- 向量库增量同步、版本快照任务
- 定时任务：每日统计 LLM 调用用量，触发超额告警

## 六、内部内网服务 SDK（不对外暴露，仅服务内部调用）

业务服务内部封装 SDK，仅在内网调用外部大模型服务商 API：

- VL 图像解析 SDK：传入图片内网地址，返回图片结构化文本
- LLM 文本生成 SDK：传入 prompt 上下文，返回回答（支持流式回调）；内置重试、熔断、多服务商自动切换

## 七、限流、熔断、降级规则

- 接入层：单身份 QPS 限制（FastAPI RateLimitMiddleware，Redis 固定窗口计数），超限返回 429
- 大模型 API 调用策略
  - 重试：最多 2 次重试
  - 熔断：连续 5 次调用失败，熔断 5 分钟，自动切换备用 API 服务商
  - 降级：熔断触发，返回提示：大模型服务暂时繁忙，请稍后重试（SSE 场景下发 `error` 事件）

## 八、业务自定义错误码附录

| code | 说明 |
| --- | --- |
| 200 | 成功 |
| 400 | 参数非法 |
| 401 | token 失效 / 未登录 |
| 403 | RBAC 权限拒绝 |
| 404 | 资源不存在 |
| 429 | 请求限流 |
| 500 | 服务内部异常 |
| 50001 | 外部大模型 API 调用失败 |
| 50002 | RAG 检索异常 |
| 50003 | 上传文件不符合要求（格式 / 大小超限） |

## 九、安全约束

- 所有用户隐私信息，在调用外部 LLM/VL API 前自动脱敏，清除姓名、身份证、手机号等敏感字段。
- 图片原始文件、问诊原始记录，仅存储在内网存储，不会上传至外部大模型服务商。
- 全部接口请求携带 traceId，全链路日志埋点，支持问题追踪与安全审计。
- refresh token 仅用于换取新 token，不可用于调用业务接口；登出后 token 进入黑名单立即失效。
