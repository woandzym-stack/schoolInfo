-- 申请快讯首版：仅新增两张表，不修改 schools、admission_changes 或其他抓取表。
-- 执行前请先核对目标 MySQL 实例与数据库，并备份数据。

CREATE TABLE IF NOT EXISTS admission_updates (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  school_id INT NOT NULL COMMENT '关联 schools.id',
  change_kind VARCHAR(30) NOT NULL DEFAULT 'other',
  title VARCHAR(120) NOT NULL DEFAULT '',
  summary VARCHAR(300) NOT NULL DEFAULT '',
  scope_text VARCHAR(500) NOT NULL DEFAULT '',
  change_detail TEXT NOT NULL,
  action_text TEXT NOT NULL,
  sources_json JSON NOT NULL COMMENT '[{name,url,support}]',
  official_published_on DATE NULL,
  verified_at DATETIME NULL COMMENT '人工核实时间，东八区',
  correction_note TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT 'draft/published/deleted',
  deleted_reason VARCHAR(500) NULL,
  first_published_at DATETIME NULL,
  content_modified_at DATETIME NULL,
  created_by INT NOT NULL COMMENT '关联 users.id',
  updated_by INT NOT NULL COMMENT '关联 users.id',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_updates_school_status_id (school_id, status, id),
  KEY idx_updates_status_first (status, first_published_at, id),
  KEY idx_updates_updated (updated_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='人工申请快讯，单当前版本';

CREATE TABLE IF NOT EXISTS admission_change_reviews (
  change_id INT NOT NULL COMMENT '关联 admission_changes.id，主键防止重复采用',
  status VARCHAR(20) NOT NULL COMMENT 'adopted/ignored；无行表示 pending',
  update_id INT UNSIGNED NULL COMMENT '采用时关联 admission_updates.id',
  reviewed_by INT NOT NULL COMMENT '关联 users.id',
  reviewed_at DATETIME NOT NULL,
  PRIMARY KEY (change_id),
  KEY idx_reviews_status (status),
  KEY idx_reviews_update (update_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='外部申请变化的轻量处置';
