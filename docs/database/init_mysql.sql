-- 智享生物 SDLC 项目管理平台 MySQL 8.0 初始化脚本
-- 基准文档：docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md

CREATE DATABASE IF NOT EXISTS intellective_bio_sdlc
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE intellective_bio_sdlc;

SET NAMES utf8mb4;
SET time_zone = '+08:00';

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户 ID',
  username VARCHAR(64) NOT NULL COMMENT '登录账号',
  full_name VARCHAR(100) NOT NULL COMMENT '姓名',
  email VARCHAR(128) NULL COMMENT '邮箱',
  mobile VARCHAR(32) NULL COMMENT '手机号',
  password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
  department VARCHAR(100) NULL COMMENT '部门',
  is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  last_login_time DATETIME NULL COMMENT '最近登录时间',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  delete_time DATETIME NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_username (username),
  KEY idx_users_full_name (full_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表';

CREATE TABLE IF NOT EXISTS roles (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '角色 ID',
  role_key VARCHAR(64) NOT NULL COMMENT '角色标识',
  role_name VARCHAR(100) NOT NULL COMMENT '角色名称',
  description VARCHAR(500) NULL COMMENT '描述',
  is_system TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否系统角色',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_roles_role_key (role_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='角色表';

CREATE TABLE IF NOT EXISTS user_roles (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户 ID',
  role_id BIGINT UNSIGNED NOT NULL COMMENT '角色 ID',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_roles_user_role (user_id, role_id),
  KEY idx_user_roles_role (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户角色关系表';

CREATE TABLE IF NOT EXISTS programs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '项目集 ID',
  parent_id BIGINT UNSIGNED NULL COMMENT '父项目集 ID',
  name VARCHAR(150) NOT NULL COMMENT '项目集名称',
  owner_id BIGINT UNSIGNED NULL COMMENT '负责人 ID',
  department VARCHAR(100) NULL COMMENT '所属部门',
  planned_start_date DATE NULL COMMENT '计划开始日期',
  planned_end_date DATE NULL COMMENT '计划结束日期',
  actual_start_date DATE NULL COMMENT '实际开始日期',
  actual_end_date DATE NULL COMMENT '实际结束日期',
  is_long_term TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否长期维护',
  status VARCHAR(32) NOT NULL DEFAULT 'planning' COMMENT '状态：planning、active、paused、closed、maintenance',
  lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段：development、maintenance',
  maintenance_start_time DATETIME NULL COMMENT '进入运维时间',
  description TEXT NULL COMMENT '描述',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  delete_time DATETIME NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  KEY idx_programs_parent (parent_id),
  KEY idx_programs_owner (owner_id),
  KEY idx_programs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目集表';

CREATE TABLE IF NOT EXISTS projects (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '项目 ID',
  parent_id BIGINT UNSIGNED NULL COMMENT '父项目 ID',
  program_id BIGINT UNSIGNED NULL COMMENT '所属项目集 ID',
  name VARCHAR(150) NOT NULL COMMENT '项目名称',
  owner_id BIGINT UNSIGNED NULL COMMENT '项目负责人 ID',
  start_date DATE NULL COMMENT '开始日期',
  end_date DATE NULL COMMENT '结束日期',
  actual_start_date DATE NULL COMMENT '实际开始日期',
  actual_end_date DATE NULL COMMENT '实际结束日期',
  is_long_term TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否长期维护',
  status VARCHAR(32) NOT NULL DEFAULT 'planning' COMMENT '状态：planning、active、paused、closed',
  description TEXT NULL COMMENT '描述',
  workflow_config_id BIGINT UNSIGNED NULL COMMENT '项目级工作流配置 ID',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  delete_time DATETIME NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  KEY idx_projects_parent (parent_id),
  KEY idx_projects_program (program_id),
  KEY idx_projects_owner (owner_id),
  KEY idx_projects_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目表';

CREATE TABLE IF NOT EXISTS project_members (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  project_id BIGINT UNSIGNED NOT NULL COMMENT '项目 ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户 ID',
  project_role VARCHAR(64) NOT NULL COMMENT '项目角色：owner、developer、tester、viewer',
  join_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_project_members_project_user (project_id, user_id),
  KEY idx_project_members_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目成员表';

CREATE TABLE IF NOT EXISTS iterations (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '迭代 ID',
  project_id BIGINT UNSIGNED NOT NULL COMMENT '所属项目 ID',
  name VARCHAR(150) NOT NULL COMMENT '迭代名称',
  owner_id BIGINT UNSIGNED NULL COMMENT '负责人 ID',
  start_date DATE NULL COMMENT '开始日期',
  end_date DATE NULL COMMENT '结束日期',
  actual_start_date DATE NULL COMMENT '实际开始日期',
  status VARCHAR(32) NOT NULL DEFAULT 'planning' COMMENT '状态：planning、active、finished、closed',
  lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段：development、maintenance',
  goal TEXT NULL COMMENT '目标说明',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  delete_time DATETIME NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  KEY idx_iterations_project (project_id),
  KEY idx_iterations_owner (owner_id),
  KEY idx_iterations_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='迭代表';

CREATE TABLE IF NOT EXISTS requirements (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '需求 ID',
  project_id BIGINT UNSIGNED NOT NULL COMMENT '所属项目 ID',
  iteration_id BIGINT UNSIGNED NULL COMMENT '所属迭代 ID',
  title VARCHAR(255) NOT NULL COMMENT '需求标题',
  requirement_type VARCHAR(64) NULL COMMENT '需求类型',
  priority VARCHAR(32) NOT NULL DEFAULT '3' COMMENT '优先级：1 最高，5 最低',
  owner_id BIGINT UNSIGNED NULL COMMENT '负责人 ID',
  proposer_id BIGINT UNSIGNED NULL COMMENT '提出人 ID',
  status VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '状态：draft、active、done、closed',
  lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段：development、maintenance',
  review_status VARCHAR(32) NOT NULL DEFAULT 'not_required' COMMENT '评审状态',
  description TEXT NULL COMMENT '需求描述',
  acceptance_criteria TEXT NULL COMMENT '验收标准',
  source_reviewed TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否评审通过',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  delete_time DATETIME NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  KEY idx_requirements_project (project_id),
  KEY idx_requirements_iteration (iteration_id),
  KEY idx_requirements_owner (owner_id),
  KEY idx_requirements_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='需求表';

CREATE TABLE IF NOT EXISTS tasks (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '任务 ID',
  project_id BIGINT UNSIGNED NOT NULL COMMENT '所属项目 ID',
  iteration_id BIGINT UNSIGNED NULL COMMENT '直接关联迭代 ID',
  requirement_id BIGINT UNSIGNED NULL COMMENT '关联需求 ID',
  title VARCHAR(255) NOT NULL COMMENT '任务标题',
  task_type VARCHAR(64) NULL COMMENT '任务类型',
  priority VARCHAR(32) NOT NULL DEFAULT 'medium' COMMENT '优先级',
  owner_id BIGINT UNSIGNED NULL COMMENT '负责人 ID',
  estimated_hours DECIMAL(10,2) NULL COMMENT '预计工时',
  actual_hours DECIMAL(10,2) NULL COMMENT '实际工时',
  due_date DATE NULL COMMENT '截止日期',
  status VARCHAR(32) NOT NULL DEFAULT 'todo' COMMENT '状态：todo、doing、done、closed',
  lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段：development、maintenance',
  description TEXT NULL COMMENT '任务描述',
  source_requirement_review_status VARCHAR(32) NULL COMMENT '生成任务时需求评审状态快照',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  delete_time DATETIME NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  KEY idx_tasks_project (project_id),
  KEY idx_tasks_iteration (iteration_id),
  KEY idx_tasks_requirement (requirement_id),
  KEY idx_tasks_owner (owner_id),
  KEY idx_tasks_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='任务表';

CREATE TABLE IF NOT EXISTS test_cases (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用例 ID',
  project_id BIGINT UNSIGNED NULL COMMENT '所属项目 ID，NULL 表示全局用例',
  requirement_id BIGINT UNSIGNED NULL COMMENT '关联需求 ID',
  title VARCHAR(255) NOT NULL COMMENT '用例标题',
  case_type VARCHAR(64) NULL COMMENT '用例类型',
  test_scope VARCHAR(64) NULL COMMENT '适用范围/测试环境',
  default_tester_id BIGINT UNSIGNED NULL COMMENT '默认测试人员',
  precondition TEXT NULL COMMENT '前置条件',
  steps_json JSON NULL COMMENT '测试步骤，结构化 JSON',
  expected_result TEXT NULL COMMENT '预期结果',
  last_execute_time DATETIME NULL COMMENT '最近执行时间',
  last_execute_result VARCHAR(32) NULL COMMENT '最近执行结果',
  status VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '状态',
  lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段：development、maintenance',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  delete_time DATETIME NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  KEY idx_test_cases_project (project_id),
  KEY idx_test_cases_requirement (requirement_id),
  KEY idx_test_cases_tester (default_tester_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='测试用例表';

CREATE TABLE IF NOT EXISTS test_case_execution_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '执行记录 ID',
  test_case_id BIGINT UNSIGNED NOT NULL COMMENT '测试用例 ID',
  executor_id BIGINT UNSIGNED NULL COMMENT '执行人 ID',
  execute_time DATETIME NOT NULL COMMENT '执行时间',
  result VARCHAR(32) NOT NULL COMMENT '执行结果：ignored、passed、failed、blocked',
  steps_result_json JSON NULL COMMENT '步骤执行结果',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_tcel_case (test_case_id),
  KEY idx_tcel_execute_time (execute_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='测试用例执行记录表';

CREATE TABLE IF NOT EXISTS test_runs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '测试单 ID',
  project_id BIGINT UNSIGNED NOT NULL COMMENT '所属项目 ID',
  iteration_id BIGINT UNSIGNED NULL COMMENT '关联迭代 ID',
  name VARCHAR(150) NOT NULL COMMENT '测试单名称',
  test_owner_id BIGINT UNSIGNED NULL COMMENT '测试负责人 ID',
  start_date DATE NULL COMMENT '开始日期',
  end_date DATE NULL COMMENT '结束日期',
  status VARCHAR(32) NOT NULL DEFAULT 'planning' COMMENT '执行状态',
  lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段：development、maintenance',
  remark TEXT NULL COMMENT '备注',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  delete_time DATETIME NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  KEY idx_test_runs_project (project_id),
  KEY idx_test_runs_iteration (iteration_id),
  KEY idx_test_runs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='测试单表';

CREATE TABLE IF NOT EXISTS test_run_cases (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  test_run_id BIGINT UNSIGNED NOT NULL COMMENT '测试单 ID',
  test_case_id BIGINT UNSIGNED NOT NULL COMMENT '测试用例 ID',
  tester_id BIGINT UNSIGNED NULL COMMENT '执行人',
  result VARCHAR(32) NOT NULL DEFAULT 'not_run' COMMENT 'not_run、passed、failed、blocked',
  execute_time DATETIME NULL COMMENT '执行时间',
  remark TEXT NULL COMMENT '执行备注',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_test_run_cases_run_case (test_run_id, test_case_id),
  KEY idx_test_run_cases_result (result),
  KEY idx_test_run_cases_tester (tester_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='测试单用例执行表';

CREATE TABLE IF NOT EXISTS bugs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Bug ID',
  project_id BIGINT UNSIGNED NOT NULL COMMENT '所属项目 ID',
  iteration_id BIGINT UNSIGNED NULL COMMENT '所属迭代 ID',
  requirement_id BIGINT UNSIGNED NULL COMMENT '关联需求 ID',
  task_id BIGINT UNSIGNED NULL COMMENT '关联任务 ID',
  test_case_id BIGINT UNSIGNED NULL COMMENT '来源用例 ID',
  test_run_id BIGINT UNSIGNED NULL COMMENT '来源测试单 ID',
  title VARCHAR(255) NOT NULL COMMENT 'Bug 标题',
  bug_type VARCHAR(64) NULL COMMENT 'Bug 类型',
  severity VARCHAR(32) NOT NULL DEFAULT '3' COMMENT '严重程度：1 最高，5 最低',
  priority VARCHAR(32) NOT NULL DEFAULT '3' COMMENT '优先级：1 最高，5 最低',
  owner_id BIGINT UNSIGNED NULL COMMENT '负责人 ID',
  reporter_id BIGINT UNSIGNED NULL COMMENT '提出人 ID',
  reproduce_steps TEXT NULL COMMENT '复现步骤',
  expected_result TEXT NULL COMMENT '期望结果',
  actual_result TEXT NULL COMMENT '实际结果',
  status VARCHAR(32) NOT NULL DEFAULT 'open' COMMENT 'open、fixing、verifying、closed、reopened',
  lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段：development、maintenance',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  delete_time DATETIME NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  KEY idx_bugs_project (project_id),
  KEY idx_bugs_iteration (iteration_id),
  KEY idx_bugs_requirement (requirement_id),
  KEY idx_bugs_task (task_id),
  KEY idx_bugs_owner (owner_id),
  KEY idx_bugs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Bug 表';

CREATE TABLE IF NOT EXISTS tags (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '标签 ID',
  tag_name VARCHAR(64) NOT NULL COMMENT '标签名称',
  color VARCHAR(32) NULL COMMENT '标签颜色',
  object_type VARCHAR(64) NOT NULL COMMENT '适用对象：test_case、bug',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_tags_object_name (object_type, tag_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='标签表';

CREATE TABLE IF NOT EXISTS object_tags (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  object_type VARCHAR(64) NOT NULL COMMENT '对象类型',
  object_id BIGINT UNSIGNED NOT NULL COMMENT '对象 ID',
  tag_id BIGINT UNSIGNED NOT NULL COMMENT '标签 ID',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_object_tags_object_tag (object_type, object_id, tag_id),
  KEY idx_object_tags_tag (tag_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='对象标签关系表';

CREATE TABLE IF NOT EXISTS attachments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '附件 ID',
  object_type VARCHAR(64) NOT NULL COMMENT '对象类型',
  object_id BIGINT UNSIGNED NOT NULL COMMENT '对象 ID',
  file_name VARCHAR(255) NOT NULL COMMENT '原始文件名',
  file_path VARCHAR(500) NOT NULL COMMENT '存储路径',
  file_size BIGINT UNSIGNED NULL COMMENT '文件大小',
  mime_type VARCHAR(128) NULL COMMENT 'MIME 类型',
  uploader_id BIGINT UNSIGNED NULL COMMENT '上传人',
  upload_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  PRIMARY KEY (id),
  KEY idx_attachments_object (object_type, object_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='附件表';

CREATE TABLE IF NOT EXISTS form_field_registry (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '字段 ID',
  object_type VARCHAR(64) NOT NULL COMMENT '对象类型',
  field_key VARCHAR(100) NOT NULL COMMENT '字段唯一标识',
  field_label VARCHAR(100) NOT NULL COMMENT '字段显示名称',
  field_type VARCHAR(64) NOT NULL COMMENT 'text、textarea、select、date、user、number、file、richtext、table',
  is_system TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否系统字段',
  is_required TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否必填',
  is_visible TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否表单展示',
  is_searchable TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否可搜索',
  is_list_visible TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否列表展示',
  options_source VARCHAR(100) NULL COMMENT '选项来源',
  default_value VARCHAR(500) NULL COMMENT '默认值',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
  validation_rules JSON NULL COMMENT '校验规则',
  business_key VARCHAR(64) NULL COMMENT '业务语义标识',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_form_field_object_key (object_type, field_key),
  KEY idx_form_field_object (object_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='字段注册表';

CREATE TABLE IF NOT EXISTS form_layout_config (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '配置 ID',
  object_type VARCHAR(64) NOT NULL COMMENT '对象类型',
  field_id BIGINT UNSIGNED NOT NULL COMMENT '字段 ID',
  group_name VARCHAR(100) NULL COMMENT '分组名称',
  width_span INT NOT NULL DEFAULT 24 COMMENT '表单栅格宽度',
  is_advanced TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否高级字段',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_form_layout_object (object_type),
  KEY idx_form_layout_field (field_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='表单布局配置表';

CREATE TABLE IF NOT EXISTS custom_field_value (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  object_type VARCHAR(64) NOT NULL COMMENT '对象类型',
  object_id BIGINT UNSIGNED NOT NULL COMMENT '对象 ID',
  field_id BIGINT UNSIGNED NOT NULL COMMENT '字段 ID',
  value_text TEXT NULL COMMENT '文本值',
  value_number DECIMAL(18,4) NULL COMMENT '数字值',
  value_date DATETIME NULL COMMENT '日期值',
  value_json JSON NULL COMMENT '复杂值',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_custom_field_value (object_type, object_id, field_id),
  KEY idx_custom_field_field (field_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='自定义字段值表';

CREATE TABLE IF NOT EXISTS workflow_rules (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '规则 ID',
  rule_name VARCHAR(150) NOT NULL COMMENT '规则名称',
  scope_type VARCHAR(32) NOT NULL COMMENT 'system、project',
  scope_id BIGINT UNSIGNED NULL COMMENT '项目 ID，系统级为空',
  target_object VARCHAR(64) NOT NULL COMMENT '适用对象',
  trigger_action VARCHAR(64) NOT NULL COMMENT '触发动作',
  condition_json JSON NULL COMMENT '条件配置',
  action_json JSON NOT NULL COMMENT '执行动作配置',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  priority INT NOT NULL DEFAULT 100 COMMENT '优先级',
  block_message VARCHAR(500) NULL COMMENT '阻断提示',
  description TEXT NULL COMMENT '描述',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  updater_id BIGINT UNSIGNED NULL COMMENT '更新人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_workflow_scope (scope_type, scope_id),
  KEY idx_workflow_target_action (target_object, trigger_action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='工作流规则表';

CREATE TABLE IF NOT EXISTS object_relation (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '关系 ID',
  source_type VARCHAR(64) NOT NULL COMMENT '来源对象类型',
  source_id BIGINT UNSIGNED NOT NULL COMMENT '来源对象 ID',
  target_type VARCHAR(64) NOT NULL COMMENT '目标对象类型',
  target_id BIGINT UNSIGNED NOT NULL COMMENT '目标对象 ID',
  relation_type VARCHAR(64) NOT NULL COMMENT 'generated、related、blocked、duplicate、depends_on、covers、executes、fixes',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_relation_source (source_type, source_id),
  KEY idx_relation_target (target_type, target_id),
  KEY idx_relation_type (relation_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='对象关联表';

CREATE TABLE IF NOT EXISTS status_operation_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '记录 ID',
  object_type VARCHAR(64) NOT NULL COMMENT '对象类型：program、project',
  object_id BIGINT UNSIGNED NOT NULL COMMENT '对象 ID',
  action VARCHAR(32) NOT NULL COMMENT '操作：start、suspend、close、activate',
  from_status VARCHAR(32) NULL COMMENT '操作前状态',
  to_status VARCHAR(32) NOT NULL COMMENT '操作后状态',
  reason VARCHAR(64) NULL COMMENT '关闭原因',
  effective_time DATETIME NOT NULL COMMENT '实际完成时间',
  remark TEXT NULL COMMENT '备注',
  actor_id BIGINT UNSIGNED NULL COMMENT '操作人 ID',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_status_operation_object (object_type, object_id),
  KEY idx_status_operation_time (effective_time),
  KEY idx_status_operation_actor (actor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='状态操作记录表';

CREATE TABLE IF NOT EXISTS notifications (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '通知 ID',
  receiver_id BIGINT UNSIGNED NOT NULL COMMENT '接收人 ID',
  title VARCHAR(200) NOT NULL COMMENT '通知标题',
  content TEXT NULL COMMENT '通知内容',
  object_type VARCHAR(64) NULL COMMENT '关联对象类型',
  object_id BIGINT UNSIGNED NULL COMMENT '关联对象 ID',
  is_read TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已读',
  read_time DATETIME NULL COMMENT '阅读时间',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_notifications_receiver (receiver_id, is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='站内通知表';

CREATE TABLE IF NOT EXISTS notification_channel_config (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '渠道 ID',
  channel_type VARCHAR(32) NOT NULL COMMENT 'in_app、dingtalk',
  channel_name VARCHAR(100) NOT NULL COMMENT '渠道名称',
  webhook_url VARCHAR(1000) NULL COMMENT '钉钉机器人 Webhook，加密存储',
  secret VARCHAR(1000) NULL COMMENT '钉钉加签密钥，加密存储',
  enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  scope_type VARCHAR(32) NOT NULL DEFAULT 'system' COMMENT 'system、project、program',
  scope_id BIGINT UNSIGNED NULL COMMENT '范围 ID',
  creator_id BIGINT UNSIGNED NULL COMMENT '创建人',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_notification_channel_scope (scope_type, scope_id),
  KEY idx_notification_channel_type (channel_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='通知渠道配置表';

CREATE TABLE IF NOT EXISTS notification_delivery_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '日志 ID',
  notification_id BIGINT UNSIGNED NULL COMMENT '站内通知 ID',
  channel_type VARCHAR(32) NOT NULL COMMENT '通知渠道',
  receiver VARCHAR(255) NULL COMMENT '接收目标',
  request_payload JSON NULL COMMENT '发送内容',
  response_body TEXT NULL COMMENT '返回结果',
  status VARCHAR(32) NOT NULL COMMENT 'success、failed、pending',
  retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数',
  send_time DATETIME NULL COMMENT '发送时间',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_delivery_notification (notification_id),
  KEY idx_delivery_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='通知发送记录表';

CREATE TABLE IF NOT EXISTS audit_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '日志 ID',
  actor_id BIGINT UNSIGNED NULL COMMENT '操作人 ID',
  action VARCHAR(64) NOT NULL COMMENT '操作类型',
  object_type VARCHAR(64) NOT NULL COMMENT '对象类型',
  object_id BIGINT UNSIGNED NULL COMMENT '对象 ID',
  before_data JSON NULL COMMENT '变更前数据',
  after_data JSON NULL COMMENT '变更后数据',
  ip_address VARCHAR(64) NULL COMMENT 'IP 地址',
  user_agent VARCHAR(500) NULL COMMENT '浏览器信息',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  PRIMARY KEY (id),
  KEY idx_audit_object (object_type, object_id),
  KEY idx_audit_actor (actor_id),
  KEY idx_audit_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='审计日志表';

CREATE TABLE IF NOT EXISTS external_integration_mapping (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '映射 ID',
  provider VARCHAR(32) NOT NULL COMMENT 'gitlab、github、jira',
  object_type VARCHAR(64) NOT NULL COMMENT '本系统对象类型',
  object_id BIGINT UNSIGNED NOT NULL COMMENT '本系统对象 ID',
  external_project_id VARCHAR(128) NULL COMMENT 'GitLab project ID',
  external_object_type VARCHAR(64) NOT NULL COMMENT 'issue、merge_request、commit、pipeline',
  external_object_id VARCHAR(128) NULL COMMENT 'GitLab 全局 ID',
  external_iid VARCHAR(128) NULL COMMENT 'GitLab 项目内 IID',
  external_url VARCHAR(1000) NULL COMMENT '外部链接',
  sync_status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '同步状态',
  last_sync_time DATETIME NULL COMMENT '最近同步时间',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_external_mapping_local (provider, object_type, object_id),
  KEY idx_external_mapping_external (provider, external_project_id, external_object_type, external_iid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='外部系统映射表';

INSERT INTO roles (role_key, role_name, description, is_system, enabled)
VALUES
  ('system_admin', '系统管理员', '系统初始化、用户、角色、基础配置', 1, 1),
  ('program_owner', '项目集负责人', '管理项目集和下属项目', 1, 1),
  ('project_owner', '项目负责人', '管理单个项目交付', 1, 1),
  ('requirement_owner', '产品/需求负责人', '维护需求', 1, 1),
  ('developer', '开发人员', '执行任务、修复 Bug', 1, 1),
  ('tester', '测试人员', '维护用例、执行测试', 1, 1),
  ('viewer', '访客/只读成员', '只读查看项目数据', 1, 1)
ON DUPLICATE KEY UPDATE
  role_name = VALUES(role_name),
  description = VALUES(description),
  enabled = VALUES(enabled);

INSERT INTO users (username, full_name, password_hash, department, is_active)
VALUES ('admin', '系统管理员', 'CHANGE_ME_WITH_BACKEND_HASH', '系统管理', 1)
ON DUPLICATE KEY UPDATE
  full_name = VALUES(full_name),
  department = VALUES(department),
  is_active = VALUES(is_active);

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
JOIN roles r ON r.role_key = 'system_admin'
WHERE u.username = 'admin'
ON DUPLICATE KEY UPDATE user_id = VALUES(user_id);

INSERT INTO notification_channel_config (channel_type, channel_name, enabled, scope_type)
VALUES ('in_app', '站内通知', 1, 'system')
ON DUPLICATE KEY UPDATE enabled = VALUES(enabled);
