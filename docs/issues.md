# 开发问题记录（Issues & Solutions）

> 本项目开发调试过程中踩过的坑与解决方案，便于复现环境与后续维护。
> 更新时间：2026-10-13

## 一、环境与工具链

### 1. `conda run` 的 `-i` 参数被吞

- 现象：`conda run -n medical pip install pytest -q -i https://...` 触发 conda 内部错误报告，pip 不执行。
- 原因：`-i` 是 `conda run` 自身的 `--interactive` flag，被 conda 解析而非透传给 pip。
- 解决：pip 已配清华源，去掉 `-i`；或直接调 `C:\conda\envs\medical\Scripts\pip.exe`。
- 附注：conda run 偶发内部崩溃时会弹交互式 `[y/N]` 报告提示，在非交互 shell 中会卡住——建议关键步骤直接用 env 目录下的可执行文件。

### 2. pytest 装在哪个环境搞混

- 现象：`python -m pytest` → `No module named pytest`，但 PATH 里的 `pytest` 能跑。
- 原因：`where pytest` 命中的是 base 环境 `C:\conda\Scripts\pytest.exe`；medical 环境最初没装 pytest，之前测试一直是 base 环境跑的（侥幸能 import 成功）。
- 解决：`conda run -n medical pip install pytest`；验证统一用 `C:\conda\envs\medical\Scripts\pytest.exe`。

### 3. PowerShell 5.1 编码坑（BOM / 中文乱码）

- 现象：
  - `Set-Content -Encoding UTF8` 写出的文件带 BOM；
  - 用 `ReadAllText` + `-replace` 修改 `.env` 中文注释后文件整体乱码（默认编码按 GBK 解 UTF-8 字节流）。
- 解决：写 UTF-8 无 BOM 一律用
  `[IO.File]::WriteAllText($f, $c, (New-Object System.Text.UTF8Encoding $false))`，或用编辑工具写文件。
- 同类坑：PowerShell 5.1 不支持 `<` 重定向（用 `cmd /c`）。

### 4. winget / gh CLI 安装失败（国内网络）

- 现象：`winget install GitHub.cli` 网络失败。
- 解决：未装 gh；GitHub 仓库通过网页创建，推送走已配置好的 SSH key（`ssh -T git@github.com` 验证身份）。
- 同类：GitHub 文件下载走 `https://gh-proxy.com/<url>`，注意校验完整性——ghproxy.net 曾返回截断文件，需校验 SHA256 / ZIP EOCD。

## 二、网络与本机服务

### 5. `localhost` 解析为 `::1` 导致 aioredis 全部超时（最坑的一个）

- 现象：限流中间件"全 200 永不 429"、health 中 redis 显示 down，但同步 Redis 操作（登录黑名单）完全正常。
- 原因链：
  1. Windows `localhost` 优先解析 `::1`；本机 Redis 5.0.14 只绑 `127.0.0.1`，`::1:6379` 连接拒绝要 ~2s（WinError 1225 延迟）。
  2. `socket_connect_timeout=2` 的预算被 `::1` 尝试耗尽 → `TimeoutError`。
  3. 限流中间件按"Redis 不可用时放行"静默降级 → 429 永不触发，bug 被掩盖。
  4. 同步 redis-py 对 getaddrinfo 地址列表逐个 fallback 所以正常——**同一 URL 同步通、异步不通，极具迷惑性**。
- 解决：`.env` 中 `REDIS_HOST=127.0.0.1`、`QDRANT_URL=http://127.0.0.1:6333`。
- 教训：依赖"故障放行"的中间件必须打 warning 日志，否则问题完全静默。

### 6. Redis 5.0 不支持 `HELLO` 命令（redis-py 6.x）

- 现象：redis-py 6.x 连接即报 `unknown command 'HELLO'`。
- 解决：`redis>=5.0,<6` + `protocol=2`。

## 三、RAG 设计与测试

### 7. mock embedding 无相关性阈值 → 无关查询也带引用

- 现象：只要库里有文档，任何查询 top-5 恒返回，`referenceDocs` 非空、prompt 注入无关片段。
- 原因：向量检索天然返回最近邻，词袋伪向量对无关文本的余弦也可能为正。
- 解决：实测分数分布（相关查询 0.21~0.23 / 无关查询 ≤0.135），加 `RAG_MIN_SCORE=0.18` 过滤。
- 后续：接真实 embedding（bge 系列 / text-embedding-v3）后需重新标定阈值。

### 8. Qdrant 测试残留状态污染断言

- 现象：`test_rag_full_flow` 间歇性失败，`chunks[0]` 命中调试脚本残留的"测试药"点。
- 原因：调试脚本 upsert 后异常退出未清理；每轮测试新增 doc 点永不清除，向量库是跨运行共享可变状态。
- 解决：`tests/test_rag.py` 加 autouse fixture，测试前 `delete_collection` + 重建。
- 教训：共享可变状态（向量库/Redis key）的测试必须自带隔离。

### 9. 限流测试怎么做才不 flaky

- 风险：套件共享 QPS=10 时测试互相挤兑；QPS 调大又测不到 429。
- 解决：
  - `tests/conftest.py` 设 `RATE_LIMIT_QPS=1000`，套件整体不被限流误伤；
  - 限流用例独立建一个 FastAPI 实例，`RateLimitMiddleware(qps=2)`，用独立 `sub` 的 JWT 身份，5 连发断言前 2 个 200、出现 429。

### 10. GET 接口用 POST 测试 → 405

- `test_rag_permission_denied` 对 `GET /rag/doc/list` 发了 POST，返回 405 而非期望的 401——纯测试笔误。

### 11. 多轮追问无主语，直接检索无关键词

- 现象："那这个药饭前吃还是饭后吃？"缺主语，直接拿去检索召回不到对应药品。
- 解决：在线链路加 `rewrite_query`——结合最近 3 轮历史把口语 query 改写为检索式（mock = 去口语填充词 + 拼接上一轮上下文；openai_compat = 真实 LLM 改写，失败兜底原 query）。

## 四、遗留告警（暂不处理）

| 告警 | 说明 | 处理计划 |
| --- | --- | --- |
| `InsecureKeyLengthWarning` | `JWT_SECRET`（23 字节）< 32 字节（RFC 7518 推荐） | 生产部署前换 ≥32 字节随机串 |
| `StarletteDeprecationWarning` | starlette testclient 提示安装 httpx2 | 上游变动，关注升级节奏 |
| conda 25.9.1 偶发内部崩溃报告 | conda run 退出时报错但命令实际已执行 | 用 env 目录直调绕开 |
| gh CLI 未安装 | 仓库创建走网页 | 如需自动化发布再装 |
