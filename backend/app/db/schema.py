from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "programs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("programs")}
    with engine.begin() as conn:
        if "parent_id" not in columns:
            conn.execute(text("ALTER TABLE programs ADD COLUMN parent_id BIGINT UNSIGNED NULL COMMENT '父项目集 ID' AFTER id"))
            conn.execute(text("CREATE INDEX idx_programs_parent ON programs (parent_id)"))
        if "planned_start_date" not in columns:
            conn.execute(text("ALTER TABLE programs ADD COLUMN planned_start_date DATE NULL COMMENT '计划开始日期' AFTER department"))
        if "planned_end_date" not in columns:
            conn.execute(text("ALTER TABLE programs ADD COLUMN planned_end_date DATE NULL COMMENT '计划结束日期' AFTER planned_start_date"))
        if "is_long_term" not in columns:
            conn.execute(text("ALTER TABLE programs ADD COLUMN is_long_term TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否长期维护' AFTER planned_end_date"))
