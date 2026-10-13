# 测试集清单

> 生成时间：2026-10-13 | 88 用例 | 覆盖率 87%（CI 门禁 75%）
> 运行：`pytest tests -q --cov=app --cov-report=term`（需 MySQL / Redis / Qdrant 本机服务）
> 环境：`C:\conda\envs\medical\Scripts\pytest.exe`（Windows）；CI 中为 ubuntu + 服务容器

## 总览

| 测试文件 | 用例数 | 覆盖模块 |
|---|---|---|
| test_smoke.py | 7 | 端到端冒烟：健康检查/登录/会话流/上传/登出 |
| test_auth.py | 6 | 登录、令牌、刷新、登出黑名单、RBAC |
| test_chat.py | 8 | 会话消息、SSE、意图路由、热点缓存集成 |
| test_intent.py | 12 | 意图规则分类与策略切换 |
| test_hot_cache.py | 8 | 热点词表/自动积累 |
| test_rag.py | 3 | RAG 上传→检索→下线全流程、限流中间件 |
| test_rag_eval.py | 2 | 检索质量门禁（recall@5、混合≥向量） |
| test_chunking.py | 8 | 文本切片边界 |
| test_openai_compat.py | 6 | OpenAI 兼容协议（SSE/VL/改写/意图） |
| test_gateway.py | 3 | 滑动窗口限流 |
| test_cache.py | 3 | Redis 两级缓存 |
| test_celery_task.py | 2 | Celery 入库任务 |
| test_scheduled.py | 6 | Celery beat：用量聚合/告警/快照/调度注册 |
| test_resilience.py | 4 | 重试/熔断/降级/外发脱敏 |
| test_privacy.py | 2 | 脱敏 |
| test_logging.py | 3 | JSON 日志与 traceId |
| test_metrics.py | 2 | Prometheus 指标与权限 |
| test_monitor.py | 3 | 用量成本、审计日志、鉴权 |

## 明细

### test_smoke.py — 端到端冒烟（7）
- `test_health` — 健康检查
- `test_login_and_info` — 登录 + 用户信息
- `test_login_wrong_password` — 错误密码
- `test_token_required` — 无令牌 401
- `test_chat_session_flow` — 建会话→发消息→列表→详情
- `test_file_upload` — 图片上传
- `test_logout_blacklist` — 登出后令牌失效

### test_auth.py — 认证授权（6）
- `test_login_success` / `test_login_wrong_password`
- `test_access_without_token`
- `test_non_admin_forbidden_from_monitor` — staff 访问 monitor 403
- `test_refresh_issues_new_token_pair` — 刷新令牌
- `test_logout_blacklists_access_token`

### test_chat.py — 问答链路（8）
- `test_sse_stream_emits_delta_and_done` — SSE delta/done 事件
- `test_answer_contains_disclaimer` — 免责声明
- `test_message_on_missing_session_404` / `test_message_requires_auth`
- `test_sse_emits_intent_event` — 首事件 intent
- `test_chat_intent_skips_retrieval` — chat 意图跳过 RAG（检索调用计数）
- `test_hot_topic_hit_skips_llm` — 热点命中零 LLM 调用
- `test_create_returns_intent_field` — create 响应 intent/hotTitle

### test_intent.py — 意图路由（12）
- `test_image_wins` — 带图优先 image
- `test_greeting_is_chat` / `test_long_greeting_not_chat`
- `test_qa_keywords` — 药学关键词判 qa
- `test_followup_with_history` / `test_followup_with_qa_keyword_is_qa` / `test_followup_without_history_is_other`
- `test_fallback_other`
- `test_off_strategy_returns_qa`
- `test_llm_strategy_uses_provider` / `test_llm_strategy_falls_back_on_error` / `test_llm_strategy_invalid_output_falls_back`

### test_hot_cache.py — 热点缓存（8）
- `test_normalize_query` — 归一化
- `test_manual_keyword_hit` — 人工词表命中
- `test_priority_wins` — 优先级裁决
- `test_disabled_topic_skipped` / `test_miss_returns_none`
- `test_auto_accumulate_hit` / `test_auto_skips_short_query` / `test_disabled_cache`

### test_rag.py — RAG 全流程（3）
- `test_rag_full_flow` — 上传→任务成功→列表→检索命中→建会话带引用→下线不检索→再上线
- `test_rag_permission_denied`
- `test_rate_limit_middleware` — 限流 429

### test_rag_eval.py — 检索质量门禁（2）
- `test_rag_recall_gate` — recall@5 ≥ 阈值
- `test_rag_hybrid_not_worse_than_vector` — 混合检索 ≥ 纯向量

### test_chunking.py — 切片（8）
- `test_clean_text_normalizes` / `test_chunk_empty_returns_empty`
- `test_short_paragraphs_merged` / `test_long_paragraph_sliding_window`
- `test_sentence_not_split_across_chunk_boundary` — 句子不拦腰截断
- `test_sliding_window_handles_unsplitable_text` — 无标点硬切
- `test_tiny_fragments_filtered` / `test_crlf_and_multiple_blank_lines`

### test_openai_compat.py — LLM 协议（6）
- `test_stream_chat_parses_sse` — SSE 解析（含 [DONE] 截断）
- `test_parse_image_builds_data_url` — VL 图片 data URL
- `test_rewrite_query_short_circuit_without_history` / `test_rewrite_query_with_history`
- `test_stream_chat_propagates_http_error`
- `test_classify_intent_payload_and_parse` — 意图分类 payload（max_tokens=10, temperature=0）

### test_gateway.py — 限流（3）
- `test_sliding_window_limits_within_window` / `test_sliding_window_recovers_after_slide` / `test_window_length_is_respected`

### test_cache.py — 缓存（3）
- `test_cache_roundtrip_and_clear` / `test_cache_miss_returns_none` / `test_embed_texts_cached_across_calls`

### test_celery_task.py — 异步入库（2）
- `test_ingest_task_success_updates_status` / `test_ingest_task_failure_records_error`

### test_scheduled.py — beat 定时任务（6）
- `test_aggregate_daily_usage` — 幂等聚合
- `test_usage_alert_skipped_when_quota_disabled` / `test_usage_alert_writes_audit_when_exceeded` / `test_usage_no_alert_under_quota`
- `test_qdrant_snapshot_backup` — 快照创建与保留
- `test_beat_schedule_registered` — 三项调度注册

### test_resilience.py — 韧性（4）
- `test_retry_recovers_from_transient_failure` — 首包重试
- `test_circuit_opens_after_consecutive_failures` / `test_breaker_recovers_after_reset`
- `test_outbound_messages_desensitized` — 外发前脱敏

### test_privacy.py — 脱敏（2）
- `test_desensitize_sensitive_entities` / `test_desensitize_messages_keeps_structure`

### test_logging.py — 日志（3）
- `test_json_formatter_emits_structured_record` / `test_json_formatter_carries_context_trace_id` / `test_json_formatter_includes_exception`

### test_metrics.py — 指标（2）
- `test_metrics_exposes_prometheus_format` / `test_metrics_requires_permission`

### test_monitor.py — 监控（3）
- `test_llm_usage_and_cost` / `test_audit_log_records_requests` / `test_monitor_requires_auth`

## 测试基建（conftest.py）

- `client` — TestClient（FastAPI app）
- `auth_headers` — admin 登录令牌
- `_clean_rag_cache`（autouse）— 每用例清空 RAG 结果缓存 + 热点自动积累（hotauto）+ 词表内存缓存
- `test_hot_cache._hot_topics_isolated`（autouse）— 词表快照隔离，测试后恢复（保护 dev 种子数据）

## 约定

- LLM 默认走 `MockProvider`（`llm_provider=mock`），不依赖外部 API
- 依赖本机服务：MySQL（会话/用量/词表）、Redis（缓存/限流）、Qdrant（向量）
- 新增用例请同步更新本文件与 README「测试」段的总数
