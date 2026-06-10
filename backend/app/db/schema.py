from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "programs" in table_names:
        columns = {column["name"] for column in inspector.get_columns("programs")}
        with engine.begin() as conn:
            if "parent_id" not in columns:
                conn.execute(text("ALTER TABLE programs ADD COLUMN parent_id BIGINT UNSIGNED NULL COMMENT '父项目集 ID' AFTER id"))
                conn.execute(text("CREATE INDEX idx_programs_parent ON programs (parent_id)"))
            if "planned_start_date" not in columns:
                conn.execute(text("ALTER TABLE programs ADD COLUMN planned_start_date DATE NULL COMMENT '计划开始日期' AFTER department"))
            if "planned_end_date" not in columns:
                conn.execute(text("ALTER TABLE programs ADD COLUMN planned_end_date DATE NULL COMMENT '计划结束日期' AFTER planned_start_date"))
            if "actual_start_date" not in columns:
                conn.execute(text("ALTER TABLE programs ADD COLUMN actual_start_date DATE NULL COMMENT '实际开始日期' AFTER planned_end_date"))
            if "actual_end_date" not in columns:
                conn.execute(text("ALTER TABLE programs ADD COLUMN actual_end_date DATE NULL COMMENT '实际结束日期' AFTER actual_start_date"))
            if "is_long_term" not in columns:
                conn.execute(text("ALTER TABLE programs ADD COLUMN is_long_term TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否长期维护' AFTER actual_end_date"))

    if "projects" in table_names:
        columns = {column["name"] for column in inspector.get_columns("projects")}
        with engine.begin() as conn:
            if "parent_id" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN parent_id BIGINT UNSIGNED NULL COMMENT '父项目 ID' AFTER id"))
                conn.execute(text("CREATE INDEX idx_projects_parent ON projects (parent_id)"))
            if "actual_start_date" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN actual_start_date DATE NULL COMMENT '实际开始日期' AFTER end_date"))
            if "actual_end_date" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN actual_end_date DATE NULL COMMENT '实际结束日期' AFTER actual_start_date"))
            if "is_long_term" not in columns:
                conn.execute(text("ALTER TABLE projects ADD COLUMN is_long_term TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否长期维护' AFTER actual_end_date"))
