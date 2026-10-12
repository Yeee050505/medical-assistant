from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "medical"
    mysql_password: str = "medical123"
    mysql_database: str = "medical"

    # Redis
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = "redis123"

    # Qdrant
    qdrant_url: str = "http://127.0.0.1:6333"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    jwt_refresh_expire_days: int = 7

    # 网关限流
    rate_limit_qps: int = 10

    # Embedding / RAG
    embedding_provider: str = "mock"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_dim: int = 64
    qdrant_collection: str = "medical_docs"
    rag_top_k: int = 5
    rag_min_score: float = 0.18
    rag_ingest_async: bool = False  # true 时走 Celery（需启动 worker）

    # LLM
    llm_provider: str = "mock"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    vl_api_key: str = ""
    vl_model: str = ""
    llm_price_prompt: float = 0.0  # 元 / 1K tokens
    llm_price_completion: float = 0.0  # 元 / 1K tokens

    # storage
    upload_dir: str = "./data/uploads"
    rag_doc_dir: str = "./data/rag_docs"

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        if not self.redis_password:
            return f"redis://{self.redis_host}:{self.redis_port}/0"
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    @staticmethod
    def _resolve(path_str: str) -> Path:
        """相对路径按项目根解析，避免 worker/服务进程 cwd 差异。"""
        p = Path(path_str)
        if not p.is_absolute():
            p = Path(__file__).resolve().parents[3] / p
        return p

    @property
    def upload_dir_path(self) -> Path:
        return self._resolve(self.upload_dir)

    @property
    def rag_doc_dir_path(self) -> Path:
        return self._resolve(self.rag_doc_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
