from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _ensure_column(engine: Engine, table: str, col: str, ddl: str, index_ddl: str | None = None) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    columns = {c["name"] for c in inspector.get_columns(table)}
    if col not in columns:
        with engine.begin() as conn:
            conn.execute(text(ddl))
            if index_ddl:
                conn.execute(text(index_ddl))


def _ensure_varchar_length(engine: Engine, table: str, col: str, minimum_length: int, ddl: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return
    column = next((item for item in inspector.get_columns(table) if item["name"] == col), None)
    if column and getattr(column["type"], "length", None) and column["type"].length < minimum_length:
        with engine.begin() as conn:
            conn.execute(text(ddl))


def ensure_runtime_schema(engine: Engine) -> None:
    inspector0 = inspect(engine)
    if "workflow_component_registry" not in inspector0.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE workflow_component_registry ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "component_key VARCHAR(100) NOT NULL COMMENT '组件唯一标识',"
                "component_type VARCHAR(32) NOT NULL COMMENT 'trigger、condition、action',"
                "component_name VARCHAR(100) NOT NULL COMMENT '组件名称',"
                "description VARCHAR(500) NULL COMMENT '描述',"
                "object_type VARCHAR(64) NULL COMMENT '适用对象',"
                "handler_key VARCHAR(100) NOT NULL COMMENT '后端 handler 标识',"
                "config_schema JSON NULL COMMENT '参数配置 schema',"
                "enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',"
                "is_system TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否系统内置',"
                "sort_order INT NOT NULL DEFAULT 100 COMMENT '排序',"
                "create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',"
                "update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',"
                "UNIQUE KEY uk_workflow_component_key (component_key),"
                "KEY idx_workflow_component_type (component_type, enabled)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工作流组件注册表'"
            ))

    if "handler_transition_rules" not in inspector0.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE handler_transition_rules ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "config_id BIGINT UNSIGNED NOT NULL COMMENT 'assignee config id',"
                "rule_type VARCHAR(32) NOT NULL DEFAULT 'advanced' COMMENT 'rule type',"
                "object_type VARCHAR(32) NOT NULL COMMENT 'object type',"
                "action VARCHAR(64) NOT NULL COMMENT 'workflow action',"
                "from_status VARCHAR(32) NULL COMMENT 'from status',"
                "to_status VARCHAR(32) NULL COMMENT 'to status',"
                "target_type VARCHAR(64) NOT NULL DEFAULT 'keep_current' COMMENT 'target type',"
                "target_roles VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'project roles',"
                "fallback_type VARCHAR(64) NOT NULL DEFAULT 'keep_current' COMMENT 'fallback type',"
                "fallback_roles VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'fallback roles',"
                "enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'enabled',"
                "create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',"
                "update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',"
                "KEY idx_htr_config (config_id),"
                "KEY idx_htr_match (config_id, rule_type, object_type, action, enabled)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='handler transition rules'"
            ))
    _ensure_column(engine, "handler_transition_rules", "rule_type",
                   "ALTER TABLE handler_transition_rules ADD COLUMN rule_type VARCHAR(32) NOT NULL DEFAULT 'advanced' COMMENT 'rule type' AFTER config_id",
                   "CREATE INDEX idx_htr_rule_type ON handler_transition_rules (config_id, rule_type, object_type, enabled)")
    _ensure_column(engine, "handler_transition_rules", "fallback_roles",
                   "ALTER TABLE handler_transition_rules ADD COLUMN fallback_roles VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'fallback roles' AFTER fallback_type")
    _ensure_varchar_length(
        engine,
        "handler_transition_rules",
        "target_type",
        64,
        "ALTER TABLE handler_transition_rules MODIFY COLUMN target_type VARCHAR(64) NOT NULL DEFAULT 'keep_current' COMMENT 'target type'",
    )
    _ensure_varchar_length(
        engine,
        "handler_transition_rules",
        "fallback_type",
        64,
        "ALTER TABLE handler_transition_rules MODIFY COLUMN fallback_type VARCHAR(64) NOT NULL DEFAULT 'keep_current' COMMENT 'fallback type'",
    )
    _ensure_column(engine, "status_operation_log", "actor_name",
                   "ALTER TABLE status_operation_log ADD COLUMN actor_name VARCHAR(100) NULL COMMENT 'actor name snapshot' AFTER actor_id")
    _ensure_column(engine, "status_operation_log", "is_delegated",
                   "ALTER TABLE status_operation_log ADD COLUMN is_delegated TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'delegated operation' AFTER actor_name")
    _ensure_column(engine, "status_operation_log", "delegated_owner_id",
                   "ALTER TABLE status_operation_log ADD COLUMN delegated_owner_id BIGINT UNSIGNED NULL COMMENT 'delegated owner id' AFTER is_delegated")
    _ensure_column(engine, "status_operation_log", "delegated_owner_name",
                   "ALTER TABLE status_operation_log ADD COLUMN delegated_owner_name VARCHAR(100) NULL COMMENT 'delegated owner name snapshot' AFTER delegated_owner_id")
    _ensure_column(engine, "status_operation_log", "delegate_reason",
                   "ALTER TABLE status_operation_log ADD COLUMN delegate_reason VARCHAR(255) NULL COMMENT 'delegate reason' AFTER delegated_owner_name")
    _ensure_column(engine, "status_operation_log", "selected_values",
                   "ALTER TABLE status_operation_log ADD COLUMN selected_values JSON NULL COMMENT 'selected form values' AFTER delegate_reason")
    _ensure_column(engine, "status_operation_log", "default_target_status",
                   "ALTER TABLE status_operation_log ADD COLUMN default_target_status VARCHAR(64) NULL COMMENT 'default target status' AFTER selected_values")
    _ensure_column(engine, "status_operation_log", "resolved_target_status",
                   "ALTER TABLE status_operation_log ADD COLUMN resolved_target_status VARCHAR(64) NULL COMMENT 'resolved target status' AFTER default_target_status")
    _ensure_column(engine, "status_operation_log", "override_reason",
                   "ALTER TABLE status_operation_log ADD COLUMN override_reason VARCHAR(255) NULL COMMENT 'override reason' AFTER resolved_target_status")
    _ensure_column(engine, "status_operation_log", "next_owner_id",
                   "ALTER TABLE status_operation_log ADD COLUMN next_owner_id BIGINT UNSIGNED NULL COMMENT 'next owner id' AFTER override_reason")
    _ensure_column(engine, "status_operation_log", "next_owner_name",
                   "ALTER TABLE status_operation_log ADD COLUMN next_owner_name VARCHAR(100) NULL COMMENT 'next owner name snapshot' AFTER next_owner_id")
    _ensure_column(engine, "status_operation_log", "blocker_messages",
                   "ALTER TABLE status_operation_log ADD COLUMN blocker_messages JSON NULL COMMENT 'blocker messages' AFTER next_owner_name")
    _ensure_column(engine, "status_operation_log", "workflow_definition_id",
                   "ALTER TABLE status_operation_log ADD COLUMN workflow_definition_id BIGINT UNSIGNED NULL COMMENT 'workflow definition id' AFTER action",
                   "CREATE INDEX ix_status_operation_log_workflow_definition_id ON status_operation_log (workflow_definition_id)")
    _ensure_column(engine, "status_operation_log", "from_state_id",
                   "ALTER TABLE status_operation_log ADD COLUMN from_state_id BIGINT UNSIGNED NULL COMMENT 'from workflow state id' AFTER workflow_definition_id",
                   "CREATE INDEX ix_status_operation_log_from_state_id ON status_operation_log (from_state_id)")
    _ensure_column(engine, "status_operation_log", "to_state_id",
                   "ALTER TABLE status_operation_log ADD COLUMN to_state_id BIGINT UNSIGNED NULL COMMENT 'to workflow state id' AFTER from_state_id",
                   "CREATE INDEX ix_status_operation_log_to_state_id ON status_operation_log (to_state_id)")
    _ensure_column(engine, "status_operation_log", "from_state_name",
                   "ALTER TABLE status_operation_log ADD COLUMN from_state_name VARCHAR(100) NULL COMMENT 'from state name snapshot' AFTER to_state_id")
    _ensure_column(engine, "status_operation_log", "to_state_name",
                   "ALTER TABLE status_operation_log ADD COLUMN to_state_name VARCHAR(100) NULL COMMENT 'to state name snapshot' AFTER from_state_name")

    if "workflow_definitions" not in inspector0.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE workflow_definitions ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "name VARCHAR(150) NOT NULL COMMENT 'workflow name',"
                "object_type VARCHAR(32) NOT NULL COMMENT 'requirement/task/bug',"
                "scope_type VARCHAR(32) NOT NULL DEFAULT 'system' COMMENT 'scope type',"
                "scope_id BIGINT UNSIGNED NULL COMMENT 'scope id',"
                "template_key VARCHAR(64) NULL COMMENT 'template key',"
                "parent_definition_id BIGINT UNSIGNED NULL COMMENT 'parent definition id',"
                "initial_state_id BIGINT UNSIGNED NULL COMMENT 'initial workflow state id',"
                "is_default_template TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'is default template',"
                "enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'enabled',"
                "version INT NOT NULL DEFAULT 1 COMMENT 'version',"
                "create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',"
                "update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',"
                "KEY idx_wfd_object_scope (object_type, scope_type, scope_id, enabled),"
                "KEY idx_wfd_template_key (template_key),"
                "KEY idx_wfd_parent_definition_id (parent_definition_id)"
                ",KEY ix_workflow_definitions_initial_state_id (initial_state_id)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='visual workflow definitions'"
            ))
    _ensure_column(engine, "workflow_definitions", "template_key",
                   "ALTER TABLE workflow_definitions ADD COLUMN template_key VARCHAR(64) NULL COMMENT 'template key' AFTER scope_id",
                   "CREATE INDEX idx_wfd_template_key ON workflow_definitions (template_key)")
    _ensure_column(engine, "workflow_definitions", "parent_definition_id",
                   "ALTER TABLE workflow_definitions ADD COLUMN parent_definition_id BIGINT UNSIGNED NULL COMMENT 'parent definition id' AFTER template_key",
                   "CREATE INDEX idx_wfd_parent_definition_id ON workflow_definitions (parent_definition_id)")
    _ensure_column(engine, "workflow_definitions", "is_default_template",
                   "ALTER TABLE workflow_definitions ADD COLUMN is_default_template TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'is default template' AFTER parent_definition_id")
    _ensure_column(engine, "workflow_definitions", "initial_state_id",
                   "ALTER TABLE workflow_definitions ADD COLUMN initial_state_id BIGINT UNSIGNED NULL COMMENT 'initial workflow state id' AFTER parent_definition_id",
                   "CREATE INDEX ix_workflow_definitions_initial_state_id ON workflow_definitions (initial_state_id)")

    if "workflow_states" not in inspector0.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE workflow_states ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "definition_id BIGINT UNSIGNED NOT NULL COMMENT 'workflow definition id',"
                "status_key VARCHAR(64) NOT NULL COMMENT 'status key',"
                "status_name VARCHAR(100) NOT NULL COMMENT 'status name',"
                "category VARCHAR(32) NOT NULL DEFAULT 'normal' COMMENT 'status category',"
                "color VARCHAR(32) NOT NULL DEFAULT '#2563eb' COMMENT 'node color',"
                "x INT NOT NULL DEFAULT 0 COMMENT 'canvas x',"
                "y INT NOT NULL DEFAULT 0 COMMENT 'canvas y',"
                "sort_order INT NOT NULL DEFAULT 100 COMMENT 'sort order',"
                "enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'enabled',"
                "create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',"
                "update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',"
                "KEY idx_wfs_definition (definition_id),"
                "KEY idx_wfs_status (definition_id, status_key)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='visual workflow states'"
            ))

    if "workflow_transitions" not in inspector0.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE workflow_transitions ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "definition_id BIGINT UNSIGNED NOT NULL COMMENT 'workflow definition id',"
                "action_key VARCHAR(64) NOT NULL COMMENT 'action key',"
                "action_name VARCHAR(100) NOT NULL COMMENT 'action name',"
                "from_status VARCHAR(64) NOT NULL COMMENT 'from status',"
                "to_status VARCHAR(64) NOT NULL COMMENT 'to status',"
                "from_state_id BIGINT UNSIGNED NULL COMMENT 'from workflow state id',"
                "to_state_id BIGINT UNSIGNED NULL COMMENT 'to workflow state id',"
                "allowed_roles VARCHAR(255) NOT NULL DEFAULT '' COMMENT 'allowed roles',"
                "handler_rule JSON NULL COMMENT 'handler rule',"
                "trigger_config JSON NULL COMMENT 'trigger config',"
                "condition_config JSON NULL COMMENT 'condition config',"
                "validator_config JSON NULL COMMENT 'validator config',"
                "post_action_config JSON NULL COMMENT 'post action config',"
                "ui_config JSON NULL COMMENT 'ui config',"
                "form_config JSON NULL COMMENT 'form config',"
                "enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'enabled',"
                "sort_order INT NOT NULL DEFAULT 100 COMMENT 'sort order',"
                "create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',"
                "update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',"
                "KEY idx_wft_definition (definition_id),"
                "KEY idx_wft_action (definition_id, action_key, from_status, to_status)"
                ",KEY ix_workflow_transitions_from_state_id (from_state_id)"
                ",KEY ix_workflow_transitions_to_state_id (to_state_id)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='visual workflow transitions'"
            ))
    _ensure_column(engine, "workflow_transitions", "ui_config",
                   "ALTER TABLE workflow_transitions ADD COLUMN ui_config JSON NULL COMMENT 'ui config' AFTER post_action_config")
    _ensure_column(engine, "workflow_transitions", "form_config",
                   "ALTER TABLE workflow_transitions ADD COLUMN form_config JSON NULL COMMENT 'form config' AFTER ui_config")
    _ensure_column(engine, "workflow_transitions", "from_state_id",
                   "ALTER TABLE workflow_transitions ADD COLUMN from_state_id BIGINT UNSIGNED NULL COMMENT 'from workflow state id' AFTER to_status",
                   "CREATE INDEX ix_workflow_transitions_from_state_id ON workflow_transitions (from_state_id)")
    _ensure_column(engine, "workflow_transitions", "to_state_id",
                   "ALTER TABLE workflow_transitions ADD COLUMN to_state_id BIGINT UNSIGNED NULL COMMENT 'to workflow state id' AFTER from_state_id",
                   "CREATE INDEX ix_workflow_transitions_to_state_id ON workflow_transitions (to_state_id)")

    _ensure_column(engine, "assignee_rule_configs", "lifecycle_status",
                   "ALTER TABLE assignee_rule_configs ADD COLUMN lifecycle_status VARCHAR(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/enabled/disabled' AFTER description",
                   "CREATE INDEX ix_assignee_rule_configs_lifecycle_status ON assignee_rule_configs (lifecycle_status)")

    _ensure_column(engine, "programs", "parent_id",
                   "ALTER TABLE programs ADD COLUMN parent_id BIGINT UNSIGNED NULL COMMENT '父项目集 ID' AFTER id",
                   "CREATE INDEX idx_programs_parent ON programs (parent_id)")
    _ensure_column(engine, "programs", "planned_start_date",
                   "ALTER TABLE programs ADD COLUMN planned_start_date DATE NULL COMMENT '计划开始日期' AFTER department")
    _ensure_column(engine, "programs", "planned_end_date",
                   "ALTER TABLE programs ADD COLUMN planned_end_date DATE NULL COMMENT '计划结束日期' AFTER planned_start_date")
    _ensure_column(engine, "programs", "actual_start_date",
                   "ALTER TABLE programs ADD COLUMN actual_start_date DATE NULL COMMENT '实际开始日期' AFTER planned_end_date")
    _ensure_column(engine, "programs", "actual_end_date",
                   "ALTER TABLE programs ADD COLUMN actual_end_date DATE NULL COMMENT '实际结束日期' AFTER actual_start_date")
    _ensure_column(engine, "programs", "is_long_term",
                   "ALTER TABLE programs ADD COLUMN is_long_term TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否长期维护' AFTER actual_end_date")
    _ensure_column(engine, "programs", "deleted",
                   "ALTER TABLE programs ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")

    _ensure_column(engine, "projects", "parent_id",
                   "ALTER TABLE projects ADD COLUMN parent_id BIGINT UNSIGNED NULL COMMENT '父项目 ID' AFTER id",
                   "CREATE INDEX idx_projects_parent ON projects (parent_id)")
    _ensure_column(engine, "projects", "actual_start_date",
                   "ALTER TABLE projects ADD COLUMN actual_start_date DATE NULL COMMENT '实际开始日期' AFTER end_date")
    _ensure_column(engine, "projects", "actual_end_date",
                   "ALTER TABLE projects ADD COLUMN actual_end_date DATE NULL COMMENT '实际结束日期' AFTER actual_start_date")
    _ensure_column(engine, "projects", "is_long_term",
                   "ALTER TABLE projects ADD COLUMN is_long_term TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否长期维护' AFTER actual_end_date")
    _ensure_column(engine, "projects", "deleted",
                   "ALTER TABLE projects ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")
    _ensure_column(engine, "projects", "assignee_rule_config_id",
                   "ALTER TABLE projects ADD COLUMN assignee_rule_config_id BIGINT UNSIGNED NULL COMMENT '责任人规则配置ID' AFTER workflow_config_id")

    _ensure_column(engine, "requirements", "source_project_id",
                   "ALTER TABLE requirements ADD COLUMN source_project_id BIGINT UNSIGNED NULL COMMENT '来源项目 ID' AFTER project_id",
                   "CREATE INDEX idx_requirements_source_project ON requirements (source_project_id)")
    _ensure_column(engine, "requirements", "workflow_definition_id",
                   "ALTER TABLE requirements ADD COLUMN workflow_definition_id BIGINT UNSIGNED NULL COMMENT 'workflow definition id' AFTER proposer_id",
                   "CREATE INDEX ix_requirements_workflow_definition_id ON requirements (workflow_definition_id)")
    _ensure_column(engine, "requirements", "current_state_id",
                   "ALTER TABLE requirements ADD COLUMN current_state_id BIGINT UNSIGNED NULL COMMENT 'current workflow state id' AFTER workflow_definition_id",
                   "CREATE INDEX ix_requirements_current_state_id ON requirements (current_state_id)")
    _ensure_column(engine, "requirements", "lifecycle_phase",
                   "ALTER TABLE requirements ADD COLUMN lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段' AFTER current_state_id")
    _ensure_column(engine, "requirements", "deleted",
                   "ALTER TABLE requirements ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")

    _ensure_column(engine, "tasks", "source_project_id",
                   "ALTER TABLE tasks ADD COLUMN source_project_id BIGINT UNSIGNED NULL COMMENT '来源项目 ID' AFTER project_id",
                   "CREATE INDEX idx_tasks_source_project ON tasks (source_project_id)")
    _ensure_column(engine, "tasks", "workflow_definition_id",
                   "ALTER TABLE tasks ADD COLUMN workflow_definition_id BIGINT UNSIGNED NULL COMMENT 'workflow definition id' AFTER owner_id",
                   "CREATE INDEX ix_tasks_workflow_definition_id ON tasks (workflow_definition_id)")
    _ensure_column(engine, "tasks", "current_state_id",
                   "ALTER TABLE tasks ADD COLUMN current_state_id BIGINT UNSIGNED NULL COMMENT 'current workflow state id' AFTER workflow_definition_id",
                   "CREATE INDEX ix_tasks_current_state_id ON tasks (current_state_id)")
    _ensure_column(engine, "tasks", "iteration_id",
                   "ALTER TABLE tasks ADD COLUMN iteration_id BIGINT UNSIGNED NULL COMMENT '直接关联迭代 ID' AFTER source_project_id",
                   "CREATE INDEX idx_tasks_iteration ON tasks (iteration_id)")
    _ensure_column(engine, "tasks", "lifecycle_phase",
                   "ALTER TABLE tasks ADD COLUMN lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段' AFTER current_state_id")
    _ensure_column(engine, "tasks", "deleted",
                   "ALTER TABLE tasks ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")

    _ensure_column(engine, "bugs", "source_project_id",
                   "ALTER TABLE bugs ADD COLUMN source_project_id BIGINT UNSIGNED NULL COMMENT '来源项目 ID' AFTER project_id",
                   "CREATE INDEX idx_bugs_source_project ON bugs (source_project_id)")
    _ensure_column(engine, "bugs", "workflow_definition_id",
                   "ALTER TABLE bugs ADD COLUMN workflow_definition_id BIGINT UNSIGNED NULL COMMENT 'workflow definition id' AFTER reporter_id",
                   "CREATE INDEX ix_bugs_workflow_definition_id ON bugs (workflow_definition_id)")
    _ensure_column(engine, "bugs", "current_state_id",
                   "ALTER TABLE bugs ADD COLUMN current_state_id BIGINT UNSIGNED NULL COMMENT 'current workflow state id' AFTER workflow_definition_id",
                   "CREATE INDEX ix_bugs_current_state_id ON bugs (current_state_id)")
    _ensure_column(engine, "bugs", "iteration_id",
                   "ALTER TABLE bugs ADD COLUMN iteration_id BIGINT UNSIGNED NULL COMMENT '迭代 ID' AFTER source_project_id",
                   "CREATE INDEX idx_bugs_iteration ON bugs (iteration_id)")
    _ensure_column(engine, "bugs", "bug_type",
                   "ALTER TABLE bugs ADD COLUMN bug_type VARCHAR(64) NULL COMMENT 'Bug 类型' AFTER title")
    _ensure_column(engine, "bugs", "lifecycle_phase",
                   "ALTER TABLE bugs ADD COLUMN lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段' AFTER current_state_id")
    _ensure_column(engine, "bugs", "resolution",
                   "ALTER TABLE bugs ADD COLUMN resolution VARCHAR(64) NULL COMMENT '解决结果' AFTER lifecycle_phase")
    _ensure_column(engine, "bugs", "resolve_time",
                   "ALTER TABLE bugs ADD COLUMN resolve_time DATETIME NULL COMMENT '解决时间' AFTER resolution")
    _ensure_column(engine, "bugs", "resolved_by",
                   "ALTER TABLE bugs ADD COLUMN resolved_by BIGINT UNSIGNED NULL COMMENT '解决人' AFTER resolve_time")
    _ensure_column(engine, "bugs", "verify_result",
                   "ALTER TABLE bugs ADD COLUMN verify_result VARCHAR(64) NULL COMMENT '验证结果' AFTER resolved_by")
    _ensure_column(engine, "bugs", "verify_time",
                   "ALTER TABLE bugs ADD COLUMN verify_time DATETIME NULL COMMENT '验证时间' AFTER verify_result")
    _ensure_column(engine, "bugs", "verified_by",
                   "ALTER TABLE bugs ADD COLUMN verified_by BIGINT UNSIGNED NULL COMMENT '验证人' AFTER verify_time")
    _ensure_column(engine, "bugs", "reopen_count",
                   "ALTER TABLE bugs ADD COLUMN reopen_count INT NOT NULL DEFAULT 0 COMMENT '重新打开次数' AFTER verified_by")
    _ensure_column(engine, "bugs", "close_reason",
                   "ALTER TABLE bugs ADD COLUMN close_reason VARCHAR(64) NULL COMMENT '关闭原因' AFTER reopen_count")
    _ensure_column(engine, "bugs", "deleted",
                   "ALTER TABLE bugs ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")

    if "object_watch" not in inspector0.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE object_watch ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "object_type VARCHAR(64) NOT NULL COMMENT 'object type',"
                "object_id BIGINT UNSIGNED NOT NULL COMMENT 'object id',"
                "user_id BIGINT UNSIGNED NOT NULL COMMENT 'watch user id',"
                "source VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT 'watch source',"
                "enabled TINYINT(1) NOT NULL DEFAULT 1 COMMENT 'enabled',"
                "create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',"
                "update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',"
                "KEY idx_object_watch_object (object_type, object_id),"
                "KEY idx_object_watch_user (user_id, enabled)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='object watch relations'"
            ))

    if "work_item_comments" not in inspector0.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE work_item_comments ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "object_type VARCHAR(64) NOT NULL COMMENT 'object type',"
                "object_id BIGINT UNSIGNED NOT NULL COMMENT 'object id',"
                "author_id BIGINT UNSIGNED NOT NULL COMMENT 'author id',"
                "body TEXT NOT NULL COMMENT 'comment body',"
                "mentioned_user_ids JSON NULL COMMENT 'mentioned user ids',"
                "mentions_metadata JSON NULL COMMENT 'mention metadata',"
                "create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'create time',"
                "update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'update time',"
                "KEY idx_work_item_comments_object (object_type, object_id),"
                "KEY idx_work_item_comments_author (author_id)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='work item comments'"
            ))

    _ensure_column(engine, "notifications", "category",
                   "ALTER TABLE notifications ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'system' COMMENT 'notification category' AFTER object_id")
    _ensure_column(engine, "notifications", "source_type",
                   "ALTER TABLE notifications ADD COLUMN source_type VARCHAR(64) NULL COMMENT 'source object type' AFTER category")
    _ensure_column(engine, "notifications", "source_id",
                   "ALTER TABLE notifications ADD COLUMN source_id BIGINT UNSIGNED NULL COMMENT 'source object id' AFTER source_type")
    _ensure_column(engine, "notifications", "metadata_json",
                   "ALTER TABLE notifications ADD COLUMN metadata_json JSON NULL COMMENT 'notification metadata' AFTER source_id")

    _ensure_column(engine, "test_cases", "source_project_id",
                   "ALTER TABLE test_cases ADD COLUMN source_project_id BIGINT UNSIGNED NULL COMMENT '来源项目 ID' AFTER project_id",
                   "CREATE INDEX idx_test_cases_source_project ON test_cases (source_project_id)")
    _ensure_column(engine, "test_cases", "iteration_id",
                   "ALTER TABLE test_cases ADD COLUMN iteration_id BIGINT UNSIGNED NULL COMMENT '直接关联迭代 ID' AFTER requirement_id",
                   "CREATE INDEX idx_test_cases_iteration ON test_cases (iteration_id)")
    _ensure_column(engine, "test_cases", "test_scope",
                   "ALTER TABLE test_cases ADD COLUMN test_scope VARCHAR(64) NULL COMMENT '适用范围/测试环境' AFTER case_type")
    _ensure_column(engine, "test_cases", "last_execute_time",
                   "ALTER TABLE test_cases ADD COLUMN last_execute_time DATETIME NULL COMMENT '最近执行时间' AFTER expected_result")
    _ensure_column(engine, "test_cases", "last_execute_result",
                   "ALTER TABLE test_cases ADD COLUMN last_execute_result VARCHAR(32) NULL COMMENT '最近执行结果' AFTER last_execute_time")
    _ensure_column(engine, "test_cases", "lifecycle_phase",
                   "ALTER TABLE test_cases ADD COLUMN lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段' AFTER status")
    _ensure_column(engine, "test_cases", "deleted",
                   "ALTER TABLE test_cases ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")

    inspector3 = inspect(engine)
    if "test_case_execution_log" not in inspector3.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE test_case_execution_log ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "test_case_id BIGINT UNSIGNED NOT NULL COMMENT '测试用例 ID',"
                "executor_id BIGINT UNSIGNED NULL COMMENT '执行人 ID',"
                "execute_time DATETIME NOT NULL COMMENT '执行时间',"
                "result VARCHAR(32) NOT NULL COMMENT '执行结果',"
                "steps_result_json JSON NULL COMMENT '步骤执行结果',"
                "create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试用例执行记录表'"
            ))
            conn.execute(text("CREATE INDEX idx_tcel_case ON test_case_execution_log (test_case_id)"))
            conn.execute(text("CREATE INDEX idx_tcel_execute_time ON test_case_execution_log (execute_time)"))

    _ensure_column(engine, "iterations", "deleted",
                   "ALTER TABLE iterations ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")
    _ensure_column(engine, "iterations", "actual_start_date",
                   "ALTER TABLE iterations ADD COLUMN actual_start_date DATE NULL COMMENT '实际开始日期' AFTER end_date")
    _ensure_column(engine, "iterations", "actual_end_date",
                   "ALTER TABLE iterations ADD COLUMN actual_end_date DATE NULL COMMENT '实际结束日期' AFTER actual_start_date")
    _ensure_column(engine, "iterations", "lifecycle_phase",
                   "ALTER TABLE iterations ADD COLUMN lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段' AFTER status")
    # Make legacy project_id column nullable (replaced by iteration_projects table)
    inspector2 = inspect(engine)
    if "iterations" in inspector2.get_table_names():
        cols = {c["name"]: c for c in inspector2.get_columns("iterations")}
        if "project_id" in cols and not cols["project_id"].get("nullable", False):
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE iterations MODIFY COLUMN project_id BIGINT UNSIGNED NULL DEFAULT NULL"))

    # Create iteration_projects junction table if missing
    inspector = inspect(engine)
    if "iteration_projects" not in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE iteration_projects ("
                "id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,"
                "iteration_id BIGINT UNSIGNED NOT NULL COMMENT '迭代 ID',"
                "project_id BIGINT UNSIGNED NOT NULL COMMENT '项目 ID'"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='迭代-项目关联表'"
            ))
            conn.execute(text("CREATE INDEX idx_ip_iteration ON iteration_projects (iteration_id)"))
            conn.execute(text("CREATE INDEX idx_ip_project ON iteration_projects (project_id)"))

    _ensure_column(engine, "test_runs", "deleted",
                   "ALTER TABLE test_runs ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")
    _ensure_column(engine, "test_runs", "lifecycle_phase",
                   "ALTER TABLE test_runs ADD COLUMN lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段' AFTER status")

    _ensure_column(engine, "users", "deleted",
                   "ALTER TABLE users ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")
    _ensure_column(engine, "users", "must_change_password",
                   "ALTER TABLE users ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否需要修改密码' AFTER is_active")
