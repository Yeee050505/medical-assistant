from prometheus_client import Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP 请求总数", ["method", "path", "status"]
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求延迟（秒）",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
LLM_CALLS = Counter("llm_calls_total", "大模型调用次数", ["api_type", "status"])
LLM_TOKENS = Counter("llm_tokens_total", "大模型 token 消耗", ["api_type", "kind"])
RAG_QUERIES = Counter("rag_queries_total", "RAG 检索次数", ["result"])
RAG_LATENCY = Histogram(
    "rag_search_duration_seconds",
    "RAG 检索延迟（秒）",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
CACHE_OPS = Counter("cache_ops_total", "缓存操作次数", ["op", "result"])


def record_http(method: str, path: str, status: int, seconds: float) -> None:
    HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
    HTTP_LATENCY.labels(method=method, path=path).observe(seconds)


def metrics_payload() -> bytes:
    return generate_latest()
