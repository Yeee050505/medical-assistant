"""add llm_usage_daily

说明：autogenerate 同时检测到 init.sql 手写索引（idx_*）与 SQLAlchemy 命名（ix_*）、
TINYINT/Integer 等历史漂移，属于已知无害差异，按项目规约仅迁移新表，不自动改既有索引。

Revision ID: d537db98abcc
Revises: 0001_init
Create Date: 2026-10-13 12:33:49.711748
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d537db98abcc"
down_revision: Union[str, Sequence[str], None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # IF NOT EXISTS：兼容“先 init.sql 后 alembic”的双轨初始化
    op.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS llm_usage_daily ("
            "  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,"
            "  stat_date DATE NOT NULL,"
            "  api_type VARCHAR(16) NOT NULL DEFAULT 'llm',"
            "  calls INT NOT NULL DEFAULT 0,"
            "  prompt_tokens INT NOT NULL DEFAULT 0,"
            "  completion_tokens INT NOT NULL DEFAULT 0,"
            "  cost DECIMAL(12,6) NOT NULL DEFAULT 0,"
            "  avg_duration_ms INT NOT NULL DEFAULT 0,"
            "  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
            "  UNIQUE KEY uk_date_api (stat_date, api_type),"
            "  KEY idx_stat_date (stat_date)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DROP TABLE IF EXISTS llm_usage_daily"))
