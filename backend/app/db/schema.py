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


def ensure_runtime_schema(engine: Engine) -> None:
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
    _ensure_column(engine, "projects", "lifecycle_phase",
                   "ALTER TABLE projects ADD COLUMN lifecycle_phase VARCHAR(32) NOT NULL DEFAULT 'development' COMMENT '生命周期阶段：development、maintenance' AFTER status")
    _ensure_column(engine, "projects", "maintenance_start_time",
                   "ALTER TABLE projects ADD COLUMN maintenance_start_time DATETIME NULL COMMENT '进入运维时间' AFTER lifecycle_phase")
    _ensure_column(engine, "projects", "deleted",
                   "ALTER TABLE projects ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")

    _ensure_column(engine, "requirements", "source_project_id",
                   "ALTER TABLE requirements ADD COLUMN source_project_id BIGINT UNSIGNED NULL COMMENT '来源项目 ID' AFTER project_id",
                   "CREATE INDEX idx_requirements_source_project ON requirements (source_project_id)")
    _ensure_column(engine, "requirements", "deleted",
                   "ALTER TABLE requirements ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")

    _ensure_column(engine, "tasks", "source_project_id",
                   "ALTER TABLE tasks ADD COLUMN source_project_id BIGINT UNSIGNED NULL COMMENT '来源项目 ID' AFTER project_id",
                   "CREATE INDEX idx_tasks_source_project ON tasks (source_project_id)")
    _ensure_column(engine, "tasks", "iteration_id",
                   "ALTER TABLE tasks ADD COLUMN iteration_id BIGINT UNSIGNED NULL COMMENT '直接关联迭代 ID' AFTER source_project_id",
                   "CREATE INDEX idx_tasks_iteration ON tasks (iteration_id)")
    _ensure_column(engine, "tasks", "deleted",
                   "ALTER TABLE tasks ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")

    _ensure_column(engine, "bugs", "source_project_id",
                   "ALTER TABLE bugs ADD COLUMN source_project_id BIGINT UNSIGNED NULL COMMENT '来源项目 ID' AFTER project_id",
                   "CREATE INDEX idx_bugs_source_project ON bugs (source_project_id)")
    _ensure_column(engine, "bugs", "deleted",
                   "ALTER TABLE bugs ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")

    _ensure_column(engine, "test_cases", "source_project_id",
                   "ALTER TABLE test_cases ADD COLUMN source_project_id BIGINT UNSIGNED NULL COMMENT '来源项目 ID' AFTER project_id",
                   "CREATE INDEX idx_test_cases_source_project ON test_cases (source_project_id)")
    _ensure_column(engine, "test_cases", "test_scope",
                   "ALTER TABLE test_cases ADD COLUMN test_scope VARCHAR(64) NULL COMMENT '适用范围/测试环境' AFTER case_type")
    _ensure_column(engine, "test_cases", "last_execute_time",
                   "ALTER TABLE test_cases ADD COLUMN last_execute_time DATETIME NULL COMMENT '最近执行时间' AFTER expected_result")
    _ensure_column(engine, "test_cases", "last_execute_result",
                   "ALTER TABLE test_cases ADD COLUMN last_execute_result VARCHAR(32) NULL COMMENT '最近执行结果' AFTER last_execute_time")
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

    _ensure_column(engine, "users", "deleted",
                   "ALTER TABLE users ADD COLUMN deleted TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否删除 0否1是' AFTER delete_time")
