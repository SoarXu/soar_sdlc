from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "programs" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("programs")}
    if "parent_id" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE programs ADD COLUMN parent_id BIGINT UNSIGNED NULL COMMENT '父项目集 ID' AFTER id"))
            conn.execute(text("CREATE INDEX idx_programs_parent ON programs (parent_id)"))
