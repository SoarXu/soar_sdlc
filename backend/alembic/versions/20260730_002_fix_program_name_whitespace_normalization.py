"""normalize only outer program-name whitespace

Revision ID: 20260730_002
Revises: 20260730_001
Create Date: 2026-07-30 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_002"
down_revision: Union[str, None] = "20260730_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "programs"
_SCOPE_COLUMN = "program_name_scope"
_NORMALIZED_COLUMN = "program_name_normalized"
_UNIQUE_INDEX = "uk_program_name_scope_normalized"
_CURRENT_NORMALIZATION_SQL = "LOWER(REGEXP_REPLACE({value}, '^[[:space:]]+|[[:space:]]+$', ''))"
_PREVIOUS_NORMALIZATION_SQL = _CURRENT_NORMALIZATION_SQL


def _is_mysql_family(bind) -> bool:
    return bind.dialect.name in {"mysql", "mariadb"}


def _duplicate_groups(bind, normalization_sql: str):
    expression = normalization_sql.format(value="name")
    return bind.execute(
        sa.text(
            "SELECT COALESCE(parent_id, 0) AS scope, "
            + expression
            + " AS normalized_name, GROUP_CONCAT(id ORDER BY id) AS ids, "
            "GROUP_CONCAT(name ORDER BY id SEPARATOR ' | ') AS names "
            "FROM programs WHERE deleted = 0 GROUP BY COALESCE(parent_id, 0), "
            + expression
            + " HAVING COUNT(*) > 1"
        )
    ).all()


def _require_no_duplicates(bind, normalization_sql: str) -> None:
    duplicates = _duplicate_groups(bind, normalization_sql)
    if not duplicates:
        return
    groups = []
    for row in duplicates:
        values = getattr(row, "_mapping", row)
        if isinstance(values, tuple):
            scope, normalized_name, ids, names = values
        else:
            scope = values["scope"]
            normalized_name = values["normalized_name"]
            ids = values["ids"]
            names = values["names"]
        groups.append(
            f"scope={scope}, normalized_name={normalized_name!r}, ids=[{ids}], names=[{names}]"
        )
    raise RuntimeError(
        "Cannot rebuild the program name uniqueness constraint because active duplicate "
        "program names exist: "
        + "; ".join(groups)
    )


def _require_canonical_contract(inspector) -> None:
    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    if {_SCOPE_COLUMN, _NORMALIZED_COLUMN} - columns:
        raise RuntimeError("Program name uniqueness columns are missing; migration 20260730_001 is required")
    indexes = inspector.get_indexes(_TABLE)
    canonical = next((index for index in indexes if index.get("name") == _UNIQUE_INDEX), None)
    if not canonical or not canonical.get("unique") or canonical.get("column_names") != [_SCOPE_COLUMN, _NORMALIZED_COLUMN]:
        raise RuntimeError("Program name uniqueness index has an incompatible definition")
    alternate = next(
        (
            index
            for index in indexes
            if index.get("name") != _UNIQUE_INDEX
            and index.get("column_names") == [_SCOPE_COLUMN, _NORMALIZED_COLUMN]
        ),
        None,
    )
    if alternate:
        raise RuntimeError(
            f"Program name index {alternate.get('name')!r} is not the required canonical index {_UNIQUE_INDEX!r}"
        )


def _rebuild_contract(normalization_sql: str) -> None:
    op.execute(sa.text(f"DROP INDEX {_UNIQUE_INDEX} ON {_TABLE}"))
    op.execute(sa.text(f"ALTER TABLE {_TABLE} DROP COLUMN {_NORMALIZED_COLUMN}"))
    op.execute(sa.text(f"ALTER TABLE {_TABLE} DROP COLUMN {_SCOPE_COLUMN}"))
    op.execute(
        sa.text(
            "ALTER TABLE programs ADD COLUMN program_name_scope "
            "BIGINT GENERATED ALWAYS AS "
            "(CASE WHEN deleted = 0 THEN COALESCE(parent_id, 0) ELSE NULL END) STORED"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE programs ADD COLUMN program_name_normalized "
            "VARCHAR(150) GENERATED ALWAYS AS "
            "(CASE WHEN deleted = 0 THEN "
            + normalization_sql.format(value="name")
            + " ELSE NULL END) STORED"
        )
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uk_program_name_scope_normalized ON programs "
            "(program_name_scope, program_name_normalized)"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_mysql_family(bind):
        return
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    _require_canonical_contract(inspector)
    _require_no_duplicates(bind, _CURRENT_NORMALIZATION_SQL)
    _rebuild_contract(_CURRENT_NORMALIZATION_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_mysql_family(bind):
        return
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    _require_canonical_contract(inspector)
    _require_no_duplicates(bind, _PREVIOUS_NORMALIZATION_SQL)
    _rebuild_contract(_PREVIOUS_NORMALIZATION_SQL)
