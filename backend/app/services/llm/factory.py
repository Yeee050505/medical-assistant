from app.core.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.mock import MockProvider
from app.services.llm.openai_compat import OpenAICompatProvider


def get_provider() -> LLMProvider:
    if settings.llm_provider == "mock" or not settings.llm_api_key:
        return MockProvider()
    return OpenAICompatProvider()
