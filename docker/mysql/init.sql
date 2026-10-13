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

-- 热点词条（意图路由 + 热点缓存：关键词任一命中直接返回预置回答）
CREATE TABLE IF NOT EXISTS hot_topic (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  title      VARCHAR(64) NOT NULL,
  keywords   TEXT NOT NULL,
  answer     TEXT NOT NULL,
  priority   INT NOT NULL DEFAULT 0,
  enabled    TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO hot_topic (title, keywords, answer, priority) VALUES
('流感高发期常用抗病毒药',
 '["奥司他韦","玛巴洛沙韦","流感吃啥药","流感吃什么药","流感特效药","达菲"]',
 '流感高发期常用抗病毒药物：\n1. 奥司他韦（磷酸奥司他韦胶囊/颗粒）：用于甲型和乙型流感的治疗，建议在症状出现 48 小时内开始用药，具体剂量与疗程请严格遵医嘱或参照说明书；\n2. 玛巴洛沙韦：单次口服即可完成疗程，适用于 12 岁及以上人群，同样建议尽早使用；\n3. 对症支持：高热可使用对乙酰氨基酚或布洛芬退热，注意多饮水、充分休息；\n4. 重要提示：以上为科普信息，不能替代医生诊疗，出现持续高热、呼吸困难等症状请立即就医。',
 100),
('布洛芬退热镇痛',
 '["布洛芬","退烧药","退热药","发烧吃什么","发热吃什么","布洛芬缓释"]',
 '布洛芬属于非甾体抗炎药（NSAID），具有解热、镇痛、抗炎作用：\n1. 适用场景：普通感冒或流感引起的发热，以及头痛、关节痛、牙痛等轻中度疼痛；\n2. 常见剂型：布洛芬缓释胶囊（持续释药）、布洛芬混悬液（儿童退热常用）；\n3. 注意事项：活动性消化道溃疡、胃出血患者禁用；服药期间避免空腹，不建议连用超过 5 天；\n4. 不良反应：常见胃部不适、恶心，偶见皮疹；症状持续或加重请及时就医。仅供参考，不能替代执业医师诊断。',
 90),
('蒙脱石散止泻',
 '["蒙脱石散","拉肚子吃什么","腹泻吃什么药","止泻药","思密达"]',
 '蒙脱石散是一种肠道黏膜保护类止泻药：\n1. 作用机制：覆盖消化道黏膜，吸附病原体和毒素，随肠蠕动排出体外；\n2. 适用场景：成人及儿童的急、慢性腹泻的对症治疗；\n3. 用法提示：建议空腹服用，与其他药物间隔至少 1-2 小时，避免影响其它药物吸收；\n4. 注意事项：腹泻期间注意补液防止脱水，若出现血便、持续高热或脱水迹象请及时就医。仅供参考，不能替代执业医师诊断。',
 80)
ON DUPLICATE KEY UPDATE title = title;

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
