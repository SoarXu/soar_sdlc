from collections.abc import Iterable, Iterator

from sqlalchemy import bindparam, inspect, text
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.business_component import (
    BusinessComponent,
    BusinessComponentMember,
    BusinessComponentTransitionRoute,
    WorkflowMigrationLog,
    WorkItemComponent,
)
from app.models.bug import Attachment, Bug, ObjectTag
from app.models.devops import DevopsCommitLink
from app.models.exception_rule import ExceptionRule
from app.models.field_registry import CustomFieldValue
from app.models.integration_mapping import ExternalIntegrationMapping
from app.models.iteration import Iteration, IterationProject
from app.models.iteration_completion_snapshot import IterationCompletionSnapshot
from app.models.notification import Notification, NotificationChannelConfig, NotificationDeliveryLog
from app.models.object_watch import ObjectWatch
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.relation import ObjectRelation
from app.models.requirement import Requirement
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_case_execution import TestCaseExecutionLog
from app.models.test_run import TestRun, TestRunCase
from app.models.work_item_comment import WorkItemComment
from app.models.work_item_iteration_history import WorkItemIterationHistory


_WORK_ITEM_MODELS = (
    ("requirement", Requirement),
    ("task", Task),
    ("bug", Bug),
    ("test_case", TestCase),
    ("test_run", TestRun),
)

_BATCH_SIZE = 500

_OBJECT_MODELS = (
    WorkflowMigrationLog,
    AuditLog,
    StatusOperationLog,
    WorkItemComment,
    ObjectWatch,
    ObjectTag,
    Attachment,
    CustomFieldValue,
    ExternalIntegrationMapping,
    DevopsCommitLink,
)

_REPORT_MODELS = (
    Project,
    IterationProject,
    Requirement,
    Task,
    Bug,
    TestCase,
    TestRun,
    TestCaseExecutionLog,
    TestRunCase,
    ProjectMember,
    ExceptionRule,
    BusinessComponent,
    BusinessComponentMember,
    BusinessComponentTransitionRoute,
    WorkItemComponent,
    *_OBJECT_MODELS,
    WorkItemIterationHistory,
    ObjectRelation,
    Notification,
    NotificationDeliveryLog,
    NotificationChannelConfig,
    IterationCompletionSnapshot,
    Iteration,
)


def _values(db: Session, column, *conditions) -> set[int]:
    return {
        int(value)
        for (value,) in db.query(column).filter(*conditions).all()
        if value is not None
    }


def _chunks(values: Iterable[int], batch_size: int = _BATCH_SIZE) -> Iterator[tuple[int, ...]]:
    materialized = tuple(sorted({int(value) for value in values}))
    for start in range(0, len(materialized), batch_size):
        yield materialized[start : start + batch_size]


def _matching_values(
    db: Session,
    result_column,
    match_column,
    match_values: Iterable[int],
    *conditions,
) -> set[int]:
    values: set[int] = set()
    batch_size = max(_BATCH_SIZE - len(conditions), 1)
    for batch in _chunks(match_values, batch_size):
        values.update(
            _values(
                db,
                result_column,
                match_column.in_(batch),
                *conditions,
            )
        )
    return values


def _matching_ids(db: Session, model, column, values: Iterable[int], *conditions) -> set[int]:
    return _matching_values(
        db,
        model.id,
        column,
        values,
        *conditions,
    )


def _typed_ids(
    db: Session,
    model,
    type_column,
    object_id_column,
    targets: dict[str, set[int]],
) -> set[int]:
    row_ids: set[int] = set()
    for object_type, object_ids in targets.items():
        row_ids.update(
            _matching_ids(
                db,
                model,
                object_id_column,
                object_ids,
                type_column == object_type,
            )
        )
    return row_ids


def _delete_ids(db: Session, model, row_ids: Iterable[int]) -> int:
    deleted = 0
    for batch in _chunks(row_ids):
        deleted += int(
            db.query(model)
            .filter(model.id.in_(batch))
            .delete(synchronize_session=False)
        )
    return deleted


def _null_references(db: Session, model, column, referenced_ids: set[int], owned_ids: set[int]) -> int:
    surviving_row_ids = _matching_ids(db, model, column, referenced_ids) - owned_ids
    updated = 0
    for batch in _chunks(surviving_row_ids, _BATCH_SIZE - 1):
        updated += int(
            db.query(model)
            .filter(
                model.id.in_(batch),
                column.is_not(None),
            )
            .update({column: None}, synchronize_session=False)
        )
    return updated


def _clear_legacy_project_pool_references(db: Session, project_ids: set[int]) -> int:
    """Clear a legacy iteration pointer when it remains in an upgraded database."""
    if not project_ids:
        return 0
    columns = {column["name"] for column in inspect(db.get_bind()).get_columns("projects")}
    if "requirement_pool_iteration_id" not in columns:
        return 0
    statement = text(
        "UPDATE projects SET requirement_pool_iteration_id = NULL "
        "WHERE id IN :project_ids"
    ).bindparams(bindparam("project_ids", expanding=True))
    return int(db.execute(statement, {"project_ids": sorted(project_ids)}).rowcount or 0)


def purge_project_data(db: Session, project_ids: set[int]) -> dict[str, int]:
    """Physically remove data owned by projects without ending the transaction."""
    target_project_ids = {int(project_id) for project_id in project_ids}
    report = {model.__tablename__: 0 for model in _REPORT_MODELS}
    if not target_project_ids:
        return report

    owned_ids = {
        object_type: _matching_ids(
            db,
            model,
            model.project_id,
            target_project_ids,
        )
        for object_type, model in _WORK_ITEM_MODELS
    }

    deleted_scope_ids = _matching_ids(
        db,
        IterationProject,
        IterationProject.project_id,
        target_project_ids,
    )
    candidate_iteration_ids = _matching_values(
            db,
            IterationProject.iteration_id,
            IterationProject.project_id,
            target_project_ids,
    )
    for object_type, model in _WORK_ITEM_MODELS:
        object_ids = owned_ids[object_type]
        if object_ids:
            candidate_iteration_ids.update(
                _matching_values(
                    db,
                    model.iteration_id,
                    model.id,
                    object_ids,
                    model.iteration_id.is_not(None),
                )
            )

    active_project_ids = _values(
        db,
        Project.id,
        Project.deleted == 0,
    ) - target_project_ids
    protected_iteration_ids = (
        _matching_values(
            db,
            IterationProject.iteration_id,
            IterationProject.project_id,
            active_project_ids,
        )
        if active_project_ids
        else set()
    )
    if active_project_ids:
        for _, model in _WORK_ITEM_MODELS:
            protected_iteration_ids.update(
                _matching_values(
                    db,
                    model.iteration_id,
                    model.project_id,
                    active_project_ids,
                    model.iteration_id.is_not(None),
                )
            )

    deleted_iteration_ids = candidate_iteration_ids - protected_iteration_ids
    deleted_scope_ids.update(
        _matching_ids(
            db,
            IterationProject,
            IterationProject.iteration_id,
            deleted_iteration_ids,
        )
    )

    component_ids = _matching_ids(
        db,
        BusinessComponent,
        BusinessComponent.project_id,
        target_project_ids,
    )
    component_ids.update(
        _matching_ids(
            db,
            BusinessComponent,
            BusinessComponent.source_project_id,
            target_project_ids,
        )
    )

    targets = {
        "project": target_project_ids,
        **owned_ids,
        "iteration": deleted_iteration_ids,
    }
    work_targets = {
        object_type: owned_ids[object_type]
        for object_type, _ in _WORK_ITEM_MODELS
    }

    object_row_ids = {
        model: _typed_ids(
            db,
            model,
            model.object_type,
            model.object_id,
            targets,
        )
        for model in _OBJECT_MODELS
    }
    deleted_comment_ids = object_row_ids[WorkItemComment]

    history_ids = _typed_ids(
        db,
        WorkItemIterationHistory,
        WorkItemIterationHistory.object_type,
        WorkItemIterationHistory.object_id,
        targets,
    )
    history_ids.update(
        _matching_ids(
            db,
            WorkItemIterationHistory,
            WorkItemIterationHistory.iteration_id,
            deleted_iteration_ids,
        )
    )

    relation_ids = _typed_ids(
        db,
        ObjectRelation,
        ObjectRelation.source_type,
        ObjectRelation.source_id,
        targets,
    )
    relation_ids.update(
        _typed_ids(
            db,
            ObjectRelation,
            ObjectRelation.target_type,
            ObjectRelation.target_id,
            targets,
        )
    )

    notification_ids = _typed_ids(
        db,
        Notification,
        Notification.object_type,
        Notification.object_id,
        targets,
    )
    notification_ids.update(
        _typed_ids(
            db,
            Notification,
            Notification.source_type,
            Notification.source_id,
            targets,
        )
    )
    notification_ids.update(
        _matching_ids(
            db,
            Notification,
            Notification.source_id,
            deleted_comment_ids,
            Notification.source_type == "work_item_comment",
        )
    )

    delivery_ids = _matching_ids(
        db,
        NotificationDeliveryLog,
        NotificationDeliveryLog.notification_id,
        notification_ids,
    )
    channel_config_ids = _matching_ids(
        db,
        NotificationChannelConfig,
        NotificationChannelConfig.scope_id,
        target_project_ids,
        NotificationChannelConfig.scope_type == "project",
    )
    execution_ids = _matching_ids(
        db,
        TestCaseExecutionLog,
        TestCaseExecutionLog.test_case_id,
        owned_ids["test_case"],
    )
    run_case_ids = _matching_ids(
        db,
        TestRunCase,
        TestRunCase.test_run_id,
        owned_ids["test_run"],
    )
    run_case_ids.update(
        _matching_ids(
            db,
            TestRunCase,
            TestRunCase.test_case_id,
            owned_ids["test_case"],
        )
    )

    work_item_component_ids = _typed_ids(
        db,
        WorkItemComponent,
        WorkItemComponent.object_type,
        WorkItemComponent.object_id,
        work_targets,
    )
    work_item_component_ids.update(
        _matching_ids(
            db,
            WorkItemComponent,
            WorkItemComponent.component_id,
            component_ids,
        )
    )
    component_member_ids = _matching_ids(
        db,
        BusinessComponentMember,
        BusinessComponentMember.component_id,
        component_ids,
    )
    component_route_ids = _matching_ids(
        db,
        BusinessComponentTransitionRoute,
        BusinessComponentTransitionRoute.component_id,
        component_ids,
    )
    project_member_ids = _matching_ids(
        db,
        ProjectMember,
        ProjectMember.project_id,
        target_project_ids,
    )
    exception_rule_ids = _matching_ids(
        db,
        ExceptionRule,
        ExceptionRule.project_id,
        target_project_ids,
    )
    snapshot_ids = _matching_ids(
        db,
        IterationCompletionSnapshot,
        IterationCompletionSnapshot.iteration_id,
        deleted_iteration_ids,
    )
    report[Task.__tablename__] += _null_references(
        db,
        Task,
        Task.requirement_id,
        owned_ids["requirement"],
        owned_ids["task"],
    )
    report[TestCase.__tablename__] += _null_references(
        db,
        TestCase,
        TestCase.requirement_id,
        owned_ids["requirement"],
        owned_ids["test_case"],
    )
    for column, object_type in (
        (Bug.requirement_id, "requirement"),
        (Bug.task_id, "task"),
        (Bug.test_case_id, "test_case"),
        (Bug.test_run_id, "test_run"),
    ):
        report[Bug.__tablename__] += _null_references(
            db,
            Bug,
            column,
            owned_ids[object_type],
            owned_ids["bug"],
        )

    for model, row_ids in (
        (NotificationDeliveryLog, delivery_ids),
        (Notification, notification_ids),
        (NotificationChannelConfig, channel_config_ids),
    ):
        report[model.__tablename__] += _delete_ids(db, model, row_ids)

    for model in _OBJECT_MODELS:
        report[model.__tablename__] += _delete_ids(db, model, object_row_ids[model])

    for model, row_ids in (
        (WorkItemIterationHistory, history_ids),
        (ObjectRelation, relation_ids),
        (TestCaseExecutionLog, execution_ids),
        (TestRunCase, run_case_ids),
        (WorkItemComponent, work_item_component_ids),
        (BusinessComponentTransitionRoute, component_route_ids),
        (BusinessComponentMember, component_member_ids),
        (BusinessComponent, component_ids),
        (ProjectMember, project_member_ids),
        (ExceptionRule, exception_rule_ids),
        (IterationProject, deleted_scope_ids),
    ):
        report[model.__tablename__] += _delete_ids(db, model, row_ids)

    for object_type, model in (
        ("bug", Bug),
        ("test_run", TestRun),
        ("test_case", TestCase),
        ("task", Task),
        ("requirement", Requirement),
    ):
        report[model.__tablename__] += _delete_ids(db, model, owned_ids[object_type])

    _clear_legacy_project_pool_references(db, target_project_ids)
    report[IterationCompletionSnapshot.__tablename__] += _delete_ids(
        db,
        IterationCompletionSnapshot,
        snapshot_ids,
    )
    report[Iteration.__tablename__] += _delete_ids(db, Iteration, deleted_iteration_ids)

    return report
