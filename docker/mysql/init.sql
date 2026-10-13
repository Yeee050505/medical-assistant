-- 医疗辅助问诊系统 初始化建表脚本（MySQL 8.0，随容器首次启动自动执行）
CREATE DATABASE IF NOT EXISTS medical DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE medical;

CREATE TABLE IF NOT EXISTS sys_user (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(64)  NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(16)  NOT NULL DEFAULT 'staff',
  status        TINYINT      NOT NULL DEFAULT 1,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_session (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id VARCHAR(32)  NOT NULL,
  user_id    BIGINT UNSIGNED NOT NULL,
  summary    VARCHAR(255) NOT NULL DEFAULT '',
  status     VARCHAR(16)  NOT NULL DEFAULT 'active',
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_session_id (session_id),
  KEY idx_user_id (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_message (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  session_id     BIGINT UNSIGNED NOT NULL,
  role           VARCHAR(16)  NOT NULL,
  content        MEDIUMTEXT   NOT NULL,
  reference_docs JSON         NULL,
  trace_id       VARCHAR(64)  NOT NULL DEFAULT '',
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_session_id (session_id, id),
  KEY idx_trace_id (trace_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS rag_doc (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  doc_id      VARCHAR(32)  NOT NULL,
  drug_name   VARCHAR(128) NOT NULL,
  version     VARCHAR(32)  NOT NULL DEFAULT '',
  file_path   VARCHAR(255) NOT NULL,
  status      VARCHAR(16)  NOT NULL DEFAULT 'processing',
  enabled     TINYINT      NOT NULL DEFAULT 1,
  error_msg   VARCHAR(512) NOT NULL DEFAULT '',
  uploader_id BIGINT UNSIGNED NOT NULL,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_doc_id (doc_id),
  KEY idx_drug_name (drug_name),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS task_record (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  task_id    VARCHAR(64) NOT NULL,
  doc_id     VARCHAR(32) NOT NULL DEFAULT '',
  type       VARCHAR(32) NOT NULL,
  status     VARCHAR(16) NOT NULL DEFAULT 'processing',
  error_msg  VARCHAR(512) NOT NULL DEFAULT '',
  created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_task_id (task_id),
  KEY idx_doc_id (doc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS llm_usage (
  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  trace_id          VARCHAR(64) NOT NULL DEFAULT '',
  user_id           BIGINT UNSIGNED NOT NULL DEFAULT 0,
  provider          VARCHAR(32) NOT NULL DEFAULT '',
  model             VARCHAR(64) NOT NULL DEFAULT '',
  api_type          VARCHAR(16) NOT NULL DEFAULT 'llm',
  prompt_tokens     INT NOT NULL DEFAULT 0,
  completion_tokens INT NOT NULL DEFAULT 0,
  cost              DECIMAL(10,6) NOT NULL DEFAULT 0,
  duration_ms       INT NOT NULL DEFAULT 0,
  status            VARCHAR(16) NOT NULL DEFAULT 'success',
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_created_at (created_at),
  KEY idx_trace_id (trace_id),
  KEY idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_log (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  trace_id   VARCHAR(64) NOT NULL DEFAULT '',
  user_id    BIGINT UNSIGNED NULL,
  method     VARCHAR(8)  NOT NULL,
  path       VARCHAR(255) NOT NULL,
  code       INT NOT NULL DEFAULT 200,
  ip         VARCHAR(45) NOT NULL DEFAULT '',
  cost_ms    INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_trace_id (trace_id),
  KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS file_object (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  file_id    VARCHAR(32) NOT NULL,
  user_id    BIGINT UNSIGNED NOT NULL,
  file_path  VARCHAR(255) NOT NULL,
  mime       VARCHAR(64) NOT NULL DEFAULT '',
  size_bytes BIGINT NOT NULL DEFAULT 0,
  biz_type   VARCHAR(16) NOT NULL DEFAULT 'chat',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_file_id (file_id),
  KEY idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 默认账号：admin / Admin@123（bcrypt 散列，部署后请立即修改）

-- 每日用量聚合（Celery beat）
CREATE TABLE IF NOT EXISTS llm_usage_daily (
  id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  stat_date          DATE NOT NULL,
  api_type           VARCHAR(16) NOT NULL DEFAULT 'llm',
  calls              INT NOT NULL DEFAULT 0,
  prompt_tokens      INT NOT NULL DEFAULT 0,
  completion_tokens  INT NOT NULL DEFAULT 0,
  cost               DECIMAL(12,6) NOT NULL DEFAULT 0,
  avg_duration_ms    INT NOT NULL DEFAULT 0,
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_date_api (stat_date, api_type),
  KEY idx_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO sys_user (username, password_hash, role)
VALUES ('admin', '$2b$12$KRyUQR8ScBAZvRJ5vgLyZ.gyefUl6gQiS8YfsIR.TtXwAhnAALMtm', 'admin')
ON DUPLICATE KEY UPDATE username = username;
