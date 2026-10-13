"""init schema: mirrors the DDL in docker/mysql/init.sql."""

from alembic import op
from sqlalchemy import text

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("CREATE TABLE IF NOT EXISTS sys_user (\n  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n  username      VARCHAR(64)  NOT NULL,\n  password_hash VARCHAR(255) NOT NULL,\n  role          VARCHAR(16)  NOT NULL DEFAULT 'staff',\n  status        TINYINT      NOT NULL DEFAULT 1,\n  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,\n  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n  UNIQUE KEY uk_username (username)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"))
    op.execute(text("CREATE TABLE IF NOT EXISTS chat_session (\n  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n  session_id VARCHAR(32)  NOT NULL,\n  user_id    BIGINT UNSIGNED NOT NULL,\n  summary    VARCHAR(255) NOT NULL DEFAULT '',\n  status     VARCHAR(16)  NOT NULL DEFAULT 'active',\n  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,\n  updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n  UNIQUE KEY uk_session_id (session_id),\n  KEY idx_user_id (user_id, created_at)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"))
    op.execute(text("CREATE TABLE IF NOT EXISTS chat_message (\n  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n  session_id     BIGINT UNSIGNED NOT NULL,\n  role           VARCHAR(16)  NOT NULL,\n  content        MEDIUMTEXT   NOT NULL,\n  reference_docs JSON         NULL,\n  trace_id       VARCHAR(64)  NOT NULL DEFAULT '',\n  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,\n  KEY idx_session_id (session_id, id),\n  KEY idx_trace_id (trace_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"))
    op.execute(text("CREATE TABLE IF NOT EXISTS rag_doc (\n  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n  doc_id      VARCHAR(32)  NOT NULL,\n  drug_name   VARCHAR(128) NOT NULL,\n  version     VARCHAR(32)  NOT NULL DEFAULT '',\n  file_path   VARCHAR(255) NOT NULL,\n  status      VARCHAR(16)  NOT NULL DEFAULT 'processing',\n  enabled     TINYINT      NOT NULL DEFAULT 1,\n  error_msg   VARCHAR(512) NOT NULL DEFAULT '',\n  uploader_id BIGINT UNSIGNED NOT NULL,\n  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,\n  updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n  UNIQUE KEY uk_doc_id (doc_id),\n  KEY idx_drug_name (drug_name),\n  KEY idx_status (status)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"))
    op.execute(text("CREATE TABLE IF NOT EXISTS task_record (\n  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n  task_id    VARCHAR(64) NOT NULL,\n  doc_id     VARCHAR(32) NOT NULL DEFAULT '',\n  type       VARCHAR(32) NOT NULL,\n  status     VARCHAR(16) NOT NULL DEFAULT 'processing',\n  error_msg  VARCHAR(512) NOT NULL DEFAULT '',\n  created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,\n  updated_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n  UNIQUE KEY uk_task_id (task_id),\n  KEY idx_doc_id (doc_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"))
    op.execute(text("CREATE TABLE IF NOT EXISTS llm_usage (\n  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n  trace_id          VARCHAR(64) NOT NULL DEFAULT '',\n  user_id           BIGINT UNSIGNED NOT NULL DEFAULT 0,\n  provider          VARCHAR(32) NOT NULL DEFAULT '',\n  model             VARCHAR(64) NOT NULL DEFAULT '',\n  api_type          VARCHAR(16) NOT NULL DEFAULT 'llm',\n  prompt_tokens     INT NOT NULL DEFAULT 0,\n  completion_tokens INT NOT NULL DEFAULT 0,\n  cost              DECIMAL(10,6) NOT NULL DEFAULT 0,\n  duration_ms       INT NOT NULL DEFAULT 0,\n  status            VARCHAR(16) NOT NULL DEFAULT 'success',\n  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n  KEY idx_created_at (created_at),\n  KEY idx_trace_id (trace_id),\n  KEY idx_user_id (user_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"))
    op.execute(text("CREATE TABLE IF NOT EXISTS audit_log (\n  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n  trace_id   VARCHAR(64) NOT NULL DEFAULT '',\n  user_id    BIGINT UNSIGNED NULL,\n  method     VARCHAR(8)  NOT NULL,\n  path       VARCHAR(255) NOT NULL,\n  code       INT NOT NULL DEFAULT 200,\n  ip         VARCHAR(45) NOT NULL DEFAULT '',\n  cost_ms    INT NOT NULL DEFAULT 0,\n  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n  KEY idx_trace_id (trace_id),\n  KEY idx_created_at (created_at)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"))
    op.execute(text("CREATE TABLE IF NOT EXISTS file_object (\n  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n  file_id    VARCHAR(32) NOT NULL,\n  user_id    BIGINT UNSIGNED NOT NULL,\n  file_path  VARCHAR(255) NOT NULL,\n  mime       VARCHAR(64) NOT NULL DEFAULT '',\n  size_bytes BIGINT NOT NULL DEFAULT 0,\n  biz_type   VARCHAR(16) NOT NULL DEFAULT 'chat',\n  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n  UNIQUE KEY uk_file_id (file_id),\n  KEY idx_user_id (user_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS `file_object`"))
    op.execute(text("DROP TABLE IF EXISTS `audit_log`"))
    op.execute(text("DROP TABLE IF EXISTS `llm_usage`"))
    op.execute(text("DROP TABLE IF EXISTS `task_record`"))
    op.execute(text("DROP TABLE IF EXISTS `rag_doc`"))
    op.execute(text("DROP TABLE IF EXISTS `chat_message`"))
    op.execute(text("DROP TABLE IF EXISTS `chat_session`"))
    op.execute(text("DROP TABLE IF EXISTS `sys_user`"))

