"""add hot_topic

说明：人工热点词条表（意图路由 + 热点缓存）。与 0002 相同风格：CREATE TABLE IF NOT EXISTS
兼容 init.sql / alembic 双轨初始化，按项目规约不迁移既有表的索引漂移。

Revision ID: a1b2c3d4e5f6
Revises: d537db98abcc
Create Date: 2026-10-13 15:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "d537db98abcc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS hot_topic ("
            "  id INT AUTO_INCREMENT PRIMARY KEY,"
            "  title VARCHAR(64) NOT NULL,"
            "  keywords TEXT NOT NULL,"
            "  answer TEXT NOT NULL,"
            "  priority INT NOT NULL DEFAULT 0,"
            "  enabled TINYINT(1) NOT NULL DEFAULT 1,"
            "  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
            "  KEY idx_enabled (enabled)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DROP TABLE IF EXISTS hot_topic"))
