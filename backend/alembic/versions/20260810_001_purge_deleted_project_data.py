"""purge business data owned by deleted projects

Revision ID: 20260810_001
Revises: 20260806_002
Create Date: 2026-08-10 10:00:00.000000
"""

from collections.abc import Iterable, Sequence
import json
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260810_001"
down_revision: Union[str, None] = "20260806_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BATCH_SIZE = 500

_WORK_ITEM_TABLES = (
    ("requirement", "requirements"),
    ("task", "tasks"),
    ("bug", "bugs"),
    ("test_case", "test_cases"),
    ("test_run", "test_runs"),
)

_OBJECT_TABLES = (
    "workflow_migration_logs",
    "audit_log",
    "status_operation_log",
    "work_item_comments",
    "object_watch",
    "object_tags",
    "attachments",
    "custom_field_value",
    "external_integration_mapping",
    "devops_commit_links",
)

_MUTATED_TABLES = (
    "projects",
    "iteration_projects",
    "requirements",
    "tasks",
    "bugs",
    "test_cases",
    "test_runs",
    "test_case_execution_log",
    "test_run_cases",
    "project_members",
    "exception_rules",
    "business_components",
    "business_component_members",
    "business_component_transition_routes",
    "work_item_components",
    *_OBJECT_TABLES,
    "work_item_iteration_history",
    "object_relation",
    "notifications",
    "notification_delivery_log",
    "notification_channel_config",
    "iteration_completion_snapshots",
    "iterations",
)


def _chunks(values: Iterable[int]) -> Iterable[tuple[int, ...]]:
    materialized = tuple(sorted({int(value) for value in values}))
    for start in range(0, len(materialized), _BATCH_SIZE):
        yield materialized[start : start + _BATCH_SIZE]


def _statement_ints(bind, statement) -> set[int]:
    return {
        int(value)
        for value in bind.execute(statement).scalars().all()
        if value is not None
    }


def _matching_values(
    bind,
    table: sa.Table,
    result_column,
    match_column,
    match_values: Iterable[int],
    *conditions,
) -> set[int]:
    values: set[int] = set()
    for batch in _chunks(match_values):
        values.update(
            _statement_ints(
                bind,
                sa.select(result_column).where(
                    match_column.in_(batch),
                    *conditions,
                ),
            )
        )
    return values


def _matching_ids(
    bind,
    table: sa.Table,
    match_column,
    match_values: Iterable[int],
    *conditions,
) -> set[int]:
    return _matching_values(
        bind,
        table,
        table.c.id,
        match_column,
        match_values,
        *conditions,
    )


def _typed_ids(
    bind,
    table: sa.Table,
    type_column,
    object_id_column,
    targets: dict[str, set[int]],
) -> set[int]:
    row_ids: set[int] = set()
    for object_type, object_ids in targets.items():
        row_ids.update(
            _matching_ids(
                bind,
                table,
                object_id_column,
                object_ids,
                type_column == object_type,
            )
        )
    return row_ids


def _affected_rows(result) -> int:
    rowcount = result.rowcount
    return int(rowcount) if rowcount is not None and rowcount > 0 else 0


def _delete_ids(bind, table: sa.Table, row_ids: Iterable[int]) -> int:
    deleted = 0
    for batch in _chunks(row_ids):
        deleted += _affected_rows(
            bind.execute(sa.delete(table).where(table.c.id.in_(batch)))
        )
    return deleted


def _null_column_for_ids(
    bind,
    table: sa.Table,
    column,
    row_ids: Iterable[int],
) -> int:
    updated = 0
    for batch in _chunks(row_ids):
        updated += _affected_rows(
            bind.execute(
                sa.update(table)
                .where(table.c.id.in_(batch), column.is_not(None))
                .values({column.name: None})
            )
        )
    return updated


def _surviving_reference_ids(
    bind,
    table: sa.Table,
    reference_column,
    referenced_ids: Iterable[int],
    owned_ids: set[int],
) -> set[int]:
    return (
        _matching_ids(bind, table, reference_column, referenced_ids)
        - owned_ids
    )


def _purge_deleted_project_data(bind) -> dict[str, int]:
    metadata = sa.MetaData()
    tables = {
        name: sa.Table(name, metadata, autoload_with=bind)
        for name in _MUTATED_TABLES
    }
    report = {name: 0 for name in _MUTATED_TABLES}

    projects = tables["projects"]
    deleted_project_ids = _statement_ints(
        bind,
        sa.select(projects.c.id).where(projects.c.deleted != 0),
    )
    active_project_ids = _statement_ints(
        bind,
        sa.select(projects.c.id).where(projects.c.deleted == 0),
    )

    owned_ids: dict[str, set[int]] = {}
    for object_type, table_name in _WORK_ITEM_TABLES:
        table = tables[table_name]
        owned_ids[object_type] = _matching_ids(
            bind,
            table,
            table.c.project_id,
            deleted_project_ids,
        )

    iteration_projects = tables["iteration_projects"]
    deleted_scope_ids = _matching_ids(
        bind,
        iteration_projects,
        iteration_projects.c.project_id,
        deleted_project_ids,
    )
    candidate_iteration_ids = _matching_values(
        bind,
        projects,
        projects.c.requirement_pool_iteration_id,
        projects.c.id,
        deleted_project_ids,
        projects.c.requirement_pool_iteration_id.is_not(None),
    )
    candidate_iteration_ids.update(
        _matching_values(
            bind,
            iteration_projects,
            iteration_projects.c.iteration_id,
            iteration_projects.c.project_id,
            deleted_project_ids,
        )
    )
    for object_type, table_name in _WORK_ITEM_TABLES:
        table = tables[table_name]
        candidate_iteration_ids.update(
            _matching_values(
                bind,
                table,
                table.c.iteration_id,
                table.c.id,
                owned_ids[object_type],
                table.c.iteration_id.is_not(None),
            )
        )

    protected_iteration_ids = _matching_values(
        bind,
        iteration_projects,
        iteration_projects.c.iteration_id,
        iteration_projects.c.project_id,
        active_project_ids,
    )
    protected_iteration_ids.update(
        _matching_values(
            bind,
            projects,
            projects.c.requirement_pool_iteration_id,
            projects.c.id,
            active_project_ids,
            projects.c.requirement_pool_iteration_id.is_not(None),
        )
    )
    for _, table_name in _WORK_ITEM_TABLES:
        table = tables[table_name]
        protected_iteration_ids.update(
            _matching_values(
                bind,
                table,
                table.c.iteration_id,
                table.c.project_id,
                active_project_ids,
                table.c.iteration_id.is_not(None),
            )
        )
    deleted_iteration_ids = candidate_iteration_ids - protected_iteration_ids
    deleted_scope_ids.update(
        _matching_ids(
            bind,
            iteration_projects,
            iteration_projects.c.iteration_id,
            deleted_iteration_ids,
        )
    )

    components = tables["business_components"]
    component_ids = _matching_ids(
        bind,
        components,
        components.c.project_id,
        deleted_project_ids,
    )
    component_ids.update(
        _matching_ids(
            bind,
            components,
            components.c.source_project_id,
            deleted_project_ids,
        )
    )

    targets = {
        "project": deleted_project_ids,
        **owned_ids,
        "iteration": deleted_iteration_ids,
    }
    work_targets = {
        object_type: owned_ids[object_type]
        for object_type, _ in _WORK_ITEM_TABLES
    }

    object_row_ids = {
        table_name: _typed_ids(
            bind,
            tables[table_name],
            tables[table_name].c.object_type,
            tables[table_name].c.object_id,
            targets,
        )
        for table_name in _OBJECT_TABLES
    }
    deleted_comment_ids = object_row_ids["work_item_comments"]

    history = tables["work_item_iteration_history"]
    history_ids = _typed_ids(
        bind,
        history,
        history.c.object_type,
        history.c.object_id,
        targets,
    )
    history_ids.update(
        _matching_ids(
            bind,
            history,
            history.c.iteration_id,
            deleted_iteration_ids,
        )
    )

    relations = tables["object_relation"]
    relation_ids = _typed_ids(
        bind,
        relations,
        relations.c.source_type,
        relations.c.source_id,
        targets,
    )
    relation_ids.update(
        _typed_ids(
            bind,
            relations,
            relations.c.target_type,
            relations.c.target_id,
            targets,
        )
    )

    notifications = tables["notifications"]
    notification_ids = _typed_ids(
        bind,
        notifications,
        notifications.c.object_type,
        notifications.c.object_id,
        targets,
    )
    notification_ids.update(
        _typed_ids(
            bind,
            notifications,
            notifications.c.source_type,
            notifications.c.source_id,
            targets,
        )
    )
    notification_ids.update(
        _matching_ids(
            bind,
            notifications,
            notifications.c.source_id,
            deleted_comment_ids,
            notifications.c.source_type == "work_item_comment",
        )
    )

    delivery_log = tables["notification_delivery_log"]
    delivery_ids = _matching_ids(
        bind,
        delivery_log,
        delivery_log.c.notification_id,
        notification_ids,
    )
    channel_config = tables["notification_channel_config"]
    channel_config_ids = _matching_ids(
        bind,
        channel_config,
        channel_config.c.scope_id,
        deleted_project_ids,
        channel_config.c.scope_type == "project",
    )

    execution_log = tables["test_case_execution_log"]
    execution_ids = _matching_ids(
        bind,
        execution_log,
        execution_log.c.test_case_id,
        owned_ids["test_case"],
    )
    run_cases = tables["test_run_cases"]
    run_case_ids = _matching_ids(
        bind,
        run_cases,
        run_cases.c.test_run_id,
        owned_ids["test_run"],
    )
    run_case_ids.update(
        _matching_ids(
            bind,
            run_cases,
            run_cases.c.test_case_id,
            owned_ids["test_case"],
        )
    )

    work_item_components = tables["work_item_components"]
    work_item_component_ids = _typed_ids(
        bind,
        work_item_components,
        work_item_components.c.object_type,
        work_item_components.c.object_id,
        work_targets,
    )
    work_item_component_ids.update(
        _matching_ids(
            bind,
            work_item_components,
            work_item_components.c.component_id,
            component_ids,
        )
    )

    component_member_ids = _matching_ids(
        bind,
        tables["business_component_members"],
        tables["business_component_members"].c.component_id,
        component_ids,
    )
    component_route_ids = _matching_ids(
        bind,
        tables["business_component_transition_routes"],
        tables["business_component_transition_routes"].c.component_id,
        component_ids,
    )
    project_member_ids = _matching_ids(
        bind,
        tables["project_members"],
        tables["project_members"].c.project_id,
        deleted_project_ids,
    )
    exception_rule_ids = _matching_ids(
        bind,
        tables["exception_rules"],
        tables["exception_rules"].c.project_id,
        deleted_project_ids,
    )
    snapshot_ids = _matching_ids(
        bind,
        tables["iteration_completion_snapshots"],
        tables["iteration_completion_snapshots"].c.iteration_id,
        deleted_iteration_ids,
    )
    project_pool_pointer_ids = _matching_ids(
        bind,
        projects,
        projects.c.id,
        deleted_project_ids,
        projects.c.requirement_pool_iteration_id.is_not(None),
    )

    task_reference_ids = _surviving_reference_ids(
        bind,
        tables["tasks"],
        tables["tasks"].c.requirement_id,
        owned_ids["requirement"],
        owned_ids["task"],
    )
    test_case_reference_ids = _surviving_reference_ids(
        bind,
        tables["test_cases"],
        tables["test_cases"].c.requirement_id,
        owned_ids["requirement"],
        owned_ids["test_case"],
    )
    bug_reference_ids = {
        column_name: _surviving_reference_ids(
            bind,
            tables["bugs"],
            tables["bugs"].c[column_name],
            owned_ids[object_type],
            owned_ids["bug"],
        )
        for column_name, object_type in (
            ("requirement_id", "requirement"),
            ("task_id", "task"),
            ("test_case_id", "test_case"),
            ("test_run_id", "test_run"),
        )
    }

    report["tasks"] += _null_column_for_ids(
        bind,
        tables["tasks"],
        tables["tasks"].c.requirement_id,
        task_reference_ids,
    )
    report["test_cases"] += _null_column_for_ids(
        bind,
        tables["test_cases"],
        tables["test_cases"].c.requirement_id,
        test_case_reference_ids,
    )
    for column_name, row_ids in bug_reference_ids.items():
        report["bugs"] += _null_column_for_ids(
            bind,
            tables["bugs"],
            tables["bugs"].c[column_name],
            row_ids,
        )

    report["notification_delivery_log"] += _delete_ids(
        bind,
        delivery_log,
        delivery_ids,
    )
    report["notifications"] += _delete_ids(bind, notifications, notification_ids)
    report["notification_channel_config"] += _delete_ids(
        bind,
        channel_config,
        channel_config_ids,
    )

    for table_name in _OBJECT_TABLES:
        report[table_name] += _delete_ids(
            bind,
            tables[table_name],
            object_row_ids[table_name],
        )
    report["work_item_iteration_history"] += _delete_ids(
        bind,
        history,
        history_ids,
    )
    report["object_relation"] += _delete_ids(bind, relations, relation_ids)
    report["test_case_execution_log"] += _delete_ids(
        bind,
        execution_log,
        execution_ids,
    )
    report["test_run_cases"] += _delete_ids(bind, run_cases, run_case_ids)
    report["work_item_components"] += _delete_ids(
        bind,
        work_item_components,
        work_item_component_ids,
    )

    report["business_component_transition_routes"] += _delete_ids(
        bind,
        tables["business_component_transition_routes"],
        component_route_ids,
    )
    report["business_component_members"] += _delete_ids(
        bind,
        tables["business_component_members"],
        component_member_ids,
    )
    report["business_components"] += _delete_ids(bind, components, component_ids)
    report["project_members"] += _delete_ids(
        bind,
        tables["project_members"],
        project_member_ids,
    )
    report["exception_rules"] += _delete_ids(
        bind,
        tables["exception_rules"],
        exception_rule_ids,
    )
    report["iteration_projects"] += _delete_ids(
        bind,
        iteration_projects,
        deleted_scope_ids,
    )

    for object_type, table_name in (
        ("bug", "bugs"),
        ("test_run", "test_runs"),
        ("test_case", "test_cases"),
        ("task", "tasks"),
        ("requirement", "requirements"),
    ):
        report[table_name] += _delete_ids(
            bind,
            tables[table_name],
            owned_ids[object_type],
        )

    report["projects"] += _null_column_for_ids(
        bind,
        projects,
        projects.c.requirement_pool_iteration_id,
        project_pool_pointer_ids,
    )
    report["iteration_completion_snapshots"] += _delete_ids(
        bind,
        tables["iteration_completion_snapshots"],
        snapshot_ids,
    )
    report["iterations"] += _delete_ids(
        bind,
        tables["iterations"],
        deleted_iteration_ids,
    )

    return report


def upgrade() -> None:
    report = _purge_deleted_project_data(op.get_bind())
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


def downgrade() -> None:
    # Physically deleted business and audit records cannot be reconstructed.
    pass
