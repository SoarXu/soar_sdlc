"""enforce active program-name uniqueness by parent scope

Revision ID: 20260730_001
Revises: 20260729_004
Create Date: 2026-07-30 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_001"
down_revision: Union[str, None] = "20260729_004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "programs"
_SCOPE_COLUMN = "program_name_scope"
_NORMALIZED_COLUMN = "program_name_normalized"
_UNIQUE_INDEX = "uk_program_name_scope_normalized"
_NORMALIZATION_SQL = (
    "LOWER(REGEXP_REPLACE({value}, '^[[:space:]]+|[[:space:]]+$', ''))"
)


def _is_mysql_family(bind) -> bool:
    return bind.dialect.name in {"mysql", "mariadb"}


def _duplicate_active_program_names(bind):
    return bind.execute(
        sa.text(
            "SELECT COALESCE(parent_id, 0) AS scope, "
            + _NORMALIZATION_SQL.format(value="name")
            + " AS normalized_name, "
            "GROUP_CONCAT(id ORDER BY id) AS ids, "
            "GROUP_CONCAT(name ORDER BY id SEPARATOR ' | ') AS names "
            "FROM programs WHERE deleted = 0 "
            "GROUP BY COALESCE(parent_id, 0), "
            + _NORMALIZATION_SQL.format(value="name")
            + " HAVING COUNT(*) > 1"
        )
    ).all()


def _format_duplicate_groups(rows) -> str:
    groups: list[str] = []
    for row in rows:
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
    return "; ".join(groups)


def _require_no_duplicate_active_program_names(bind) -> None:
    duplicates = _duplicate_active_program_names(bind)
    if duplicates:
        raise RuntimeError(
            "Cannot add the program name uniqueness constraint because active duplicate "
            "program names exist: "
            + _format_duplicate_groups(duplicates)
        )


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_mysql_family(bind):
        return

    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    indexes = inspector.get_indexes(_TABLE)
    matching_index = next(
        (index for index in indexes if index.get("name") == _UNIQUE_INDEX),
        None,
    )
    if matching_index:
        if (
            matching_index.get("unique")
            and matching_index.get("column_names") == [_SCOPE_COLUMN, _NORMALIZED_COLUMN]
        ):
            return
        raise RuntimeError(
            f"Program name index {_UNIQUE_INDEX!r} has an incompatible definition; "
            f"expected a unique index on ({_SCOPE_COLUMN}, {_NORMALIZED_COLUMN})"
        )
    alternate_index = next(
        (
            index
            for index in indexes
            if index.get("column_names") == [_SCOPE_COLUMN, _NORMALIZED_COLUMN]
        ),
        None,
    )
    if alternate_index:
        raise RuntimeError(
            f"Program name index {alternate_index.get('name')!r} is not the required "
            f"canonical index {_UNIQUE_INDEX!r}"
        )

    _require_no_duplicate_active_program_names(bind)
    if _SCOPE_COLUMN not in columns:
        op.execute(
            sa.text(
                "ALTER TABLE programs ADD COLUMN program_name_scope "
                "BIGINT GENERATED ALWAYS AS "
                "(CASE WHEN deleted = 0 THEN COALESCE(parent_id, 0) ELSE NULL END) STORED"
            )
        )
    if _NORMALIZED_COLUMN not in columns:
        op.execute(
            sa.text(
                "ALTER TABLE programs ADD COLUMN program_name_normalized "
                "VARCHAR(150) GENERATED ALWAYS AS "
                "(CASE WHEN deleted = 0 THEN "
                "LOWER(REGEXP_REPLACE(name, '^[[:space:]]+|[[:space:]]+$', '')) "
                "ELSE NULL END) STORED"
            )
        )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uk_program_name_scope_normalized ON programs "
            "(program_name_scope, program_name_normalized)"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_mysql_family(bind):
        return

    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    indexes = inspector.get_indexes(_TABLE)
    if any(index.get("name") == _UNIQUE_INDEX for index in indexes):
        op.execute(sa.text(f"DROP INDEX {_UNIQUE_INDEX} ON {_TABLE}"))

    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    if _NORMALIZED_COLUMN in columns:
        op.execute(sa.text(f"ALTER TABLE {_TABLE} DROP COLUMN {_NORMALIZED_COLUMN}"))
    if _SCOPE_COLUMN in columns:
        op.execute(sa.text(f"ALTER TABLE {_TABLE} DROP COLUMN {_SCOPE_COLUMN}"))
