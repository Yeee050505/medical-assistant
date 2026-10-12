import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.monitor import LlmUsage

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """粗略 token 估算（约 4 字符/token）；接入真实 tokenizer 后替换。"""
    return max(1, len(text) // 4)


def record_usage(
    *,
    trace_id: str = "",
    user_id: int = 0,
    api_type: str = "llm",
    prompt_text: str,
    completion_text: str,
    duration_ms: int,
    status: str = "success",
) -> None:
    try:
        prompt_tokens = estimate_tokens(prompt_text)
        completion_tokens = estimate_tokens(completion_text)
        cost = (
            prompt_tokens / 1000 * float(settings.llm_price_prompt)
            + completion_tokens / 1000 * float(settings.llm_price_completion)
        )
        with SessionLocal() as db:
            db.add(
                LlmUsage(
                    trace_id=trace_id or "",
                    user_id=user_id or 0,
                    provider=settings.llm_provider or "mock",
                    model=settings.llm_model or "mock",
                    api_type=api_type,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost=cost,
                    duration_ms=duration_ms,
                    status=status,
                )
            )
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("写入 llm_usage 失败: %s", exc)
