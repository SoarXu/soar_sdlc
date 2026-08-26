from datetime import date, datetime, time

from sqlalchemy import Integer, and_, case, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.devops import DevopsCodeReviewTask, DevopsCommit, DevopsCommitLink, WorkItemReviewRound
from app.models.iteration import Iteration
from app.models.object_watch import ObjectWatch
from app.models.program import Program
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.user import User
from app.models.work_item_comment import WorkItemComment
from app.models.workflow_definition import WorkflowState, WorkflowTransition
from app.services.exception_center_service import list_exception_refs
from app.services.project_permission_service import is_system_admin
from app.services.role_capability_service import role_ids_for_capabilities
from app.services.project_team_service import workbench_project_ids_for_user
from app.services.workflow_state_query_service import (
    current_state_name,
    is_terminal_state,
    non_terminal_state_clause,
    terminal_state_clause,
)
from app.views.dashboard_view import (
    DashboardSummary,
    WorkbenchItem,
    WorkbenchItemPage,
    WorkbenchResponse,
    WorkbenchSection,
)


WORKBENCH_OBJECT_TYPES = {"requirement", "task", "bug"}


def get_dashboard_summary(db: Session) -> DashboardSummary:
    return DashboardSummary(
        programs=_count_active(db, Program),
        projects=_count_active(db, Project),
        requirements=_count_active(db, Requirement),
        tasks=_count_active(db, Task),
        open_bugs=db.query(func.count(Bug.id)).filter(Bug.deleted == 0, non_terminal_state_clause(Bug)).scalar()
        or 0,
    )


def get_workbench(db: Session, user_id: int | None = None) -> WorkbenchResponse:
    team_project_ids = workbench_project_ids_for_user(db, user_id) if user_id else set()
    role_ids = _role_ids_for_user(db, user_id, team_project_ids)
    view_mode = _workbench_view_mode(db, user_id, role_ids)
    scoped_project_ids = team_project_ids
    projects = {item.id: item for item in db.query(Project).filter(Project.deleted == 0).all()}
    iteration_names = {item.id: item.name for item in db.query(Iteration).filter(Iteration.deleted == 0).all()}
    active_iteration_ids = _active_iteration_ids(db)
    project_scope_ids = None if user_id and view_mode == "all" else scoped_project_ids
    active_iteration_items = _active_iteration_items(
        db,
        projects,
        iteration_names,
        project_scope_ids,
        _in_progress_iteration_ids(db),
    )
    pending_items = _pending_handling_items(
        db, projects, iteration_names, user_id, project_scope_ids, active_iteration_ids
    )
    unassigned_items = _unassigned_items(
        db, projects, iteration_names, project_scope_ids, active_iteration_ids
    )
    terminal_items = _terminal_items(db, projects, iteration_names, project_scope_ids, active_iteration_ids)
    completed_items = [item for item in terminal_items if item.terminal_kind == "completed"]
    terminated_items = [item for item in terminal_items if item.terminal_kind == "terminated"]
    created_items = _created_by_me_items(
        db, projects, iteration_names, user_id, project_scope_ids, active_iteration_ids
    )
    watched_items = _watched_by_me_items(
        db, projects, iteration_names, user_id, project_scope_ids, active_iteration_ids
    )
    mentioned_items = _mentioned_me_items(
        db, projects, iteration_names, user_id, project_scope_ids, active_iteration_ids
    )
    exception_items = _exception_center_items(
        db, projects, iteration_names, project_scope_ids, active_iteration_ids
    )
    review_tasks = _filter_review_tasks_for_role(_review_tasks(db), user_id, view_mode)
    work_item_reviews = _work_item_reviews(db, user_id)
    owner_ids = {
        item.owner_id
        for section in [
            active_iteration_items,
            pending_items,
            unassigned_items,
            completed_items,
            terminated_items,
            created_items,
            watched_items,
            mentioned_items,
            exception_items,
        ]
        for item in section
        if item.owner_id
    }
    owner_ids.update(item.mentioned_comment_author_id for item in mentioned_items if item.mentioned_comment_author_id)
    owner_ids.update(item.get("owner_id") for item in review_tasks if item.get("owner_id"))
    owner_ids.update(item.get("reviewer_id") for item in work_item_reviews if item.get("reviewer_id"))
    owners = [
        {"id": user.id, "full_name": user.full_name}
        for user in db.query(User).filter(User.deleted == 0, User.id.in_(owner_ids)).order_by(User.full_name.asc()).all()
    ] if owner_ids else []
    return WorkbenchResponse(
        active_iteration_items=active_iteration_items,
        pending_handling=WorkbenchSection(label="待处理", items=pending_items, total=len(pending_items)),
        unassigned=WorkbenchSection(label="未分派", items=unassigned_items, total=len(unassigned_items)),
        completed=WorkbenchSection(label="已完成", items=completed_items, total=len(completed_items)),
        terminated=WorkbenchSection(label="已终止", items=terminated_items, total=len(terminated_items)),
        created_by_me=WorkbenchSection(label="我发起的", items=created_items, total=len(created_items)),
        watched_by_me=WorkbenchSection(label="我关注的", items=watched_items, total=len(watched_items)),
        mentioned_me=WorkbenchSection(label="提到我的", items=mentioned_items, total=len(mentioned_items)),
        exception_center=WorkbenchSection(label="异常中心", items=exception_items, total=len(exception_items)),
        owners=owners,
        review_tasks=review_tasks,
        work_item_reviews=work_item_reviews,
        role_ids=role_ids,
        view_mode=view_mode,
    )


def get_workbench_items(
    db: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    project_ids: list[int] | None = None,
    iteration_ids: list[int] | None = None,
    object_types: list[str] | None = None,
    state_ids: list[int] | None = None,
    priorities: list[str] | None = None,
    handler_ids: list[int] | None = None,
) -> WorkbenchItemPage:
    team_project_ids = workbench_project_ids_for_user(db, user_id)
    role_ids = _role_ids_for_user(db, user_id, team_project_ids)
    scoped_project_ids = None if _workbench_view_mode(db, user_id, role_ids) == "all" else team_project_ids
    if scoped_project_ids == set():
        return WorkbenchItemPage(page=1, page_size=page_size, filter_options=_empty_workbench_filter_options())

    active_iteration_ids = _in_progress_iteration_ids(db)
    if not active_iteration_ids:
        return WorkbenchItemPage(page=1, page_size=page_size, filter_options=_empty_workbench_filter_options())

    base_query = _workbench_items_query(active_iteration_ids, scoped_project_ids)
    filter_options = _workbench_filter_options(db, base_query)
    filtered_query = _filter_workbench_items_query(
        base_query,
        keyword=keyword,
        project_ids=project_ids,
        iteration_ids=iteration_ids,
        object_types=object_types,
        state_ids=state_ids,
        priorities=priorities,
        handler_ids=handler_ids,
    )
    total = db.execute(select(func.count()).select_from(filtered_query.subquery())).scalar_one()
    page_count = max(1, (total + page_size - 1) // page_size)
    normalized_page = min(page, page_count)
    rows = db.execute(
        filtered_query
        .order_by(*_workbench_sort_columns(filtered_query))
        .offset((normalized_page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    return WorkbenchItemPage(
        items=[_workbench_page_item(row) for row in rows],
        total=total,
        page=normalized_page,
        page_size=page_size,
        page_count=page_count,
        filter_options=filter_options,
    )


def _workbench_items_query(active_iteration_ids: set[int], scoped_project_ids: set[int] | None):
    items = _workbench_item_union(active_iteration_ids).subquery("active_workbench_items")
    query = (
        select(
            items,
            Project.name.label("project_name"),
            Iteration.name.label("iteration_name"),
            WorkflowState.status_name.label("status_name"),
            WorkflowState.category.label("state_category"),
            WorkflowState.terminal_kind.label("terminal_kind"),
        )
        .select_from(items)
        .join(Project, (Project.id == items.c.project_id) & (Project.deleted == 0))
        .join(Iteration, (Iteration.id == items.c.iteration_id) & (Iteration.deleted == 0))
        .join(WorkflowState, WorkflowState.id == items.c.current_state_id)
    )
    if scoped_project_ids is not None:
        query = query.where(items.c.project_id.in_(scoped_project_ids))
    return query


def _workbench_item_union(active_iteration_ids: set[int]):
    task_iteration_id = func.coalesce(Task.iteration_id, Requirement.iteration_id)
    requirement_rows = select(
        literal("requirement").label("object_type"),
        Requirement.id.label("id"),
        Requirement.project_id.label("project_id"),
        Requirement.iteration_id.label("iteration_id"),
        Requirement.title.label("title"),
        Requirement.owner_id.label("owner_id"),
        Requirement.current_state_id.label("current_state_id"),
        Requirement.priority.label("priority"),
        literal(None).label("due_date"),
        Requirement.create_time.label("create_time"),
        Requirement.update_time.label("update_time"),
        Requirement.creator_id.label("creator_id"),
        Requirement.id.label("requirement_id"),
        literal(None).label("task_id"),
        literal(None).label("bug_type"),
        literal(None).label("severity"),
    ).where(Requirement.deleted == 0, Requirement.iteration_id.in_(active_iteration_ids))
    task_rows = (
        select(
            literal("task").label("object_type"),
            Task.id.label("id"),
            Task.project_id.label("project_id"),
            task_iteration_id.label("iteration_id"),
            Task.title.label("title"),
            Task.owner_id.label("owner_id"),
            Task.current_state_id.label("current_state_id"),
            Task.priority.label("priority"),
            Task.due_date.label("due_date"),
            Task.create_time.label("create_time"),
            Task.update_time.label("update_time"),
            Task.creator_id.label("creator_id"),
            Task.requirement_id.label("requirement_id"),
            Task.id.label("task_id"),
            literal(None).label("bug_type"),
            literal(None).label("severity"),
        )
        .select_from(Task)
        .outerjoin(Requirement, (Requirement.id == Task.requirement_id) & (Requirement.deleted == 0))
        .where(Task.deleted == 0, task_iteration_id.in_(active_iteration_ids))
    )
    bug_rows = select(
        literal("bug").label("object_type"),
        Bug.id.label("id"),
        Bug.project_id.label("project_id"),
        Bug.iteration_id.label("iteration_id"),
        Bug.title.label("title"),
        Bug.owner_id.label("owner_id"),
        Bug.current_state_id.label("current_state_id"),
        Bug.priority.label("priority"),
        literal(None).label("due_date"),
        Bug.create_time.label("create_time"),
        Bug.update_time.label("update_time"),
        Bug.creator_id.label("creator_id"),
        Bug.requirement_id.label("requirement_id"),
        Bug.task_id.label("task_id"),
        Bug.bug_type.label("bug_type"),
        Bug.severity.label("severity"),
    ).where(Bug.deleted == 0, Bug.iteration_id.in_(active_iteration_ids))
    return union_all(requirement_rows, task_rows, bug_rows)


def _filter_workbench_items_query(query, **filters):
    items = query.selected_columns
    if filters["project_ids"]:
        query = query.where(items.project_id.in_(filters["project_ids"]))
    if filters["iteration_ids"]:
        query = query.where(items.iteration_id.in_(filters["iteration_ids"]))
    if filters["object_types"]:
        query = query.where(items.object_type.in_(set(filters["object_types"]) & WORKBENCH_OBJECT_TYPES))
    if filters["state_ids"]:
        query = query.where(items.current_state_id.in_(filters["state_ids"]))
    if filters["priorities"]:
        query = query.where(items.priority.in_(filters["priorities"]))
    if filters["handler_ids"]:
        query = query.where(items.owner_id.in_(filters["handler_ids"]))
    normalized_keyword = (filters["keyword"] or "").strip().lower()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.where(
            or_(
                func.lower(items.title).like(pattern),
                func.lower(items.project_name).like(pattern),
                func.lower(items.iteration_name).like(pattern),
            )
        )
    return query


def _workbench_filter_options(db: Session, query) -> dict[str, list[dict]]:
    items = query.subquery("workbench_filter_items")
    def distinct_options(value, label):
        return [
            {"value": row.value, "label": row.label}
            for row in db.execute(
                select(value.label("value"), label.label("label"))
                .where(value.is_not(None))
                .distinct()
                .order_by(label.asc(), value.asc())
            ).mappings().all()
        ]
    return {
        "projects": distinct_options(items.c.project_id, items.c.project_name),
        "iterations": distinct_options(items.c.iteration_id, items.c.iteration_name),
        "statuses": distinct_options(items.c.current_state_id, items.c.status_name),
        "priorities": distinct_options(items.c.priority, items.c.priority),
        "handlers": distinct_options(items.c.owner_id, select(User.full_name).where(User.id == items.c.owner_id).scalar_subquery()),
    }


def _empty_workbench_filter_options() -> dict[str, list[dict]]:
    return {key: [] for key in ("projects", "iterations", "statuses", "priorities", "handlers")}


def _workbench_sort_columns(query):
    items = query.selected_columns
    terminal_order = case((items.state_category == "terminal", 1), else_=0)
    overdue_order = case(
        (and_(items.due_date.is_not(None), items.due_date < date.today()), 1),
        else_=0,
    )
    priority_order = case(
        (items.priority == "high", 1),
        (items.priority == "medium", 3),
        (items.priority == "low", 5),
        (items.priority.in_(("1", "2", "3", "4", "5")), cast(items.priority, Integer)),
        else_=99,
    )
    return (
        terminal_order.asc(),
        overdue_order.desc(),
        priority_order.asc(),
        items.due_date.is_(None).asc(),
        items.due_date.asc(),
        items.update_time.desc(),
        items.object_type.asc(),
        items.id.asc(),
    )


def _workbench_page_item(row) -> WorkbenchItem:
    return WorkbenchItem(
        id=row["id"],
        object_type=row["object_type"],
        title=row["title"],
        project_id=row["project_id"],
        project_name=row["project_name"],
        iteration_id=row["iteration_id"],
        iteration_name=row["iteration_name"],
        owner_id=row["owner_id"],
        handler_id=row["owner_id"],
        iteration_group_key=str(row["iteration_id"]),
        status=row["status_name"],
        current_state_id=row["current_state_id"],
        status_name=row["status_name"],
        state_category=row["state_category"],
        terminal_kind=row["terminal_kind"],
        priority=row["priority"],
        due_date=_date_value(row["due_date"]),
        overdue_hours=_overdue_hours(row["due_date"]),
        create_time=_datetime_value(row["create_time"]),
        update_time=_datetime_value(row["update_time"]),
        creator_id=row["creator_id"],
        requirement_id=row["requirement_id"],
        task_id=row["task_id"],
        bug_type=row["bug_type"],
        severity=row["severity"],
    )


def _active_iteration_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    scoped_project_ids: set[int] | None,
    active_iteration_ids: set[int],
) -> list[WorkbenchItem]:
    if not active_iteration_ids or scoped_project_ids == set():
        return []

    items = [
        _requirement_item(item, projects, iteration_names)
        for item in db.query(Requirement)
        .filter(Requirement.deleted == 0, Requirement.iteration_id.in_(active_iteration_ids))
        .all()
        if _in_project_scope(item.project_id, scoped_project_ids)
    ]
    effective_iteration_id = func.coalesce(Task.iteration_id, Requirement.iteration_id)
    task_query = (
        db.query(Task, effective_iteration_id.label("effective_iteration_id"))
        .outerjoin(
            Requirement,
            (Requirement.id == Task.requirement_id) & (Requirement.deleted == 0),
        )
        .filter(
            Task.deleted == 0,
            effective_iteration_id.in_(active_iteration_ids),
        )
    )
    if scoped_project_ids is not None:
        task_query = task_query.filter(Task.project_id.in_(scoped_project_ids))
    items.extend(
        _task_item(item, projects, iteration_names, resolved_iteration_id)
        for item, resolved_iteration_id in task_query.all()
    )
    items.extend(
        _bug_item(item, projects, iteration_names)
        for item in db.query(Bug)
        .filter(Bug.deleted == 0, Bug.iteration_id.in_(active_iteration_ids))
        .all()
        if _in_project_scope(item.project_id, scoped_project_ids)
    )
    return _dedup_and_sort_workbench_items(items)


def _pending_handling_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    user_id: int | None,
    scoped_project_ids: set[int] | None,
    active_iteration_ids: set[int],
) -> list[WorkbenchItem]:
    if not user_id:
        return []
    items = [
        _requirement_item(item, projects, iteration_names)
        for item in db.query(Requirement).filter(Requirement.deleted == 0, Requirement.owner_id == user_id).all()
        if not is_terminal_state(item)
        and item.iteration_id in active_iteration_ids
        and _in_project_scope(item.project_id, scoped_project_ids)
    ]
    items.extend(
        _task_item(item, projects, iteration_names, _effective_task_iteration_id(db, item))
        for item in db.query(Task).filter(Task.deleted == 0, Task.owner_id == user_id).all()
        if not is_terminal_state(item)
        and _effective_task_iteration_id(db, item) in active_iteration_ids
        and _in_project_scope(item.project_id, scoped_project_ids)
    )
    items.extend(
        _bug_item(item, projects, iteration_names)
        for item in db.query(Bug).filter(Bug.deleted == 0, Bug.owner_id == user_id).all()
        if not is_terminal_state(item)
        and item.iteration_id in active_iteration_ids
        and _in_project_scope(item.project_id, scoped_project_ids)
    )
    return _sort_workbench_items(items)


def _unassigned_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    scoped_project_ids: set[int] | None,
    active_iteration_ids: set[int],
) -> list[WorkbenchItem]:
    items = [
        _requirement_item(item, projects, iteration_names)
        for item in db.query(Requirement).filter(Requirement.deleted == 0, Requirement.owner_id.is_(None)).all()
        if not is_terminal_state(item)
        and item.iteration_id in active_iteration_ids
        and _in_project_scope(item.project_id, scoped_project_ids)
    ]
    items.extend(
        _task_item(item, projects, iteration_names, _effective_task_iteration_id(db, item))
        for item in db.query(Task).filter(Task.deleted == 0, Task.owner_id.is_(None)).all()
        if not is_terminal_state(item)
        and _effective_task_iteration_id(db, item) in active_iteration_ids
        and _in_project_scope(item.project_id, scoped_project_ids)
    )
    items.extend(
        _bug_item(item, projects, iteration_names)
        for item in db.query(Bug).filter(Bug.deleted == 0, Bug.owner_id.is_(None)).all()
        if not is_terminal_state(item)
        and item.iteration_id in active_iteration_ids
        and _in_project_scope(item.project_id, scoped_project_ids)
    )
    return _sort_workbench_items(items)


def _terminal_items(db, projects, iteration_names, scoped_project_ids, active_iteration_ids):
    items = [
        _requirement_item(item, projects, iteration_names)
        for item in db.query(Requirement).filter(Requirement.deleted == 0, terminal_state_clause(Requirement)).all()
        if item.iteration_id in active_iteration_ids and _in_project_scope(item.project_id, scoped_project_ids)
    ]
    items.extend(
        _task_item(item, projects, iteration_names, _effective_task_iteration_id(db, item))
        for item in db.query(Task).filter(Task.deleted == 0, terminal_state_clause(Task)).all()
        if _effective_task_iteration_id(db, item) in active_iteration_ids and _in_project_scope(item.project_id, scoped_project_ids)
    )
    items.extend(
        _bug_item(item, projects, iteration_names)
        for item in db.query(Bug).filter(Bug.deleted == 0, terminal_state_clause(Bug)).all()
        if item.iteration_id in active_iteration_ids and _in_project_scope(item.project_id, scoped_project_ids)
    )
    return _sort_workbench_items(items)


def _created_by_me_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    user_id: int | None,
    scoped_project_ids: set[int] | None,
    active_iteration_ids: set[int],
) -> list[WorkbenchItem]:
    if not user_id:
        return []
    items = [
        _requirement_item(item, projects, iteration_names)
        for item in db.query(Requirement).filter(
            Requirement.deleted == 0,
            Requirement.creator_id == user_id,
        ).all()
        if item.iteration_id in active_iteration_ids
        and _in_project_scope(item.project_id, scoped_project_ids)
    ]
    items.extend(
        _task_item(item, projects, iteration_names, _effective_task_iteration_id(db, item))
        for item in db.query(Task).filter(Task.deleted == 0, Task.creator_id == user_id).all()
        if _effective_task_iteration_id(db, item) in active_iteration_ids and _in_project_scope(item.project_id, scoped_project_ids)
    )
    items.extend(
        _bug_item(item, projects, iteration_names)
        for item in db.query(Bug).filter(Bug.deleted == 0, Bug.creator_id == user_id).all()
        if item.iteration_id in active_iteration_ids
        and _in_project_scope(item.project_id, scoped_project_ids)
    )
    return _dedup_and_sort_workbench_items(items)


def _watched_by_me_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    user_id: int | None,
    scoped_project_ids: set[int] | None,
    active_iteration_ids: set[int],
) -> list[WorkbenchItem]:
    if not user_id:
        return []
    refs = [
        {
            "object_type": row.object_type,
            "id": row.object_id,
            "watch_source": row.source,
        }
        for row in db.query(ObjectWatch)
        .filter(ObjectWatch.user_id == user_id, ObjectWatch.enabled == True)  # noqa: E712
        .order_by(ObjectWatch.id.desc())
        .all()
    ]
    return _filter_active_scoped_items(
        _load_workbench_items_by_refs(db, projects, iteration_names, refs),
        scoped_project_ids,
        active_iteration_ids,
    )


def _mentioned_me_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    user_id: int | None,
    scoped_project_ids: set[int] | None,
    active_iteration_ids: set[int],
) -> list[WorkbenchItem]:
    if not user_id:
        return []
    refs = []
    for comment in db.query(WorkItemComment).order_by(WorkItemComment.id.desc()).all():
        mentioned_user_ids = comment.mentioned_user_ids or []
        if user_id not in mentioned_user_ids:
            continue
        refs.append(
            {
                "object_type": comment.object_type,
                "id": comment.object_id,
                "mentioned_in_comment_id": comment.id,
                "mentioned_comment_id": comment.id,
                "mentioned_comment_body": comment.body,
                "mentioned_comment_author_id": comment.author_id,
                "mentioned_comment_create_time": _datetime_value(comment.create_time),
            }
        )
    items = _filter_active_scoped_items(
        _load_workbench_items_by_refs(db, projects, iteration_names, refs, preserve_duplicates=True),
        scoped_project_ids,
        active_iteration_ids,
    )
    return sorted(
        items,
        key=lambda item: (item.mentioned_comment_create_time or "", item.mentioned_comment_id or 0),
        reverse=True,
    )


def _exception_center_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    scoped_project_ids: set[int] | None,
    active_iteration_ids: set[int],
) -> list[WorkbenchItem]:
    refs = list_exception_refs(db, scoped_project_ids)
    active_items = _filter_active_scoped_items(
        _load_workbench_items_by_refs(db, projects, iteration_names, refs),
        scoped_project_ids,
        active_iteration_ids,
    )
    integrity_refs = [
        ref for ref in refs
        if ref.get("exception_key") in {
            "owner_required_missing",
            "owner_ineligible",
            "iteration_history_inconsistent",
            "missing_reactivation_audit",
            "terminal_iteration_snapshot_mismatch",
        }
    ]
    integrity_refs = [*_terminal_iteration_open_item_refs(db, scoped_project_ids), *integrity_refs]
    integrity_items = _load_workbench_items_by_refs(db, projects, iteration_names, integrity_refs)
    # Active items were loaded from the complete ref set, so keep them as the
    # final value when the same object is also present in the integrity scan.
    return _dedup_and_sort_workbench_items([*integrity_items, *active_items])


def _terminal_iteration_open_item_refs(
    db: Session,
    scoped_project_ids: set[int] | None,
) -> list[dict]:
    if scoped_project_ids == set():
        return []

    terminal_iteration_ids = select(Iteration.id).where(
        Iteration.deleted == 0,
        terminal_state_clause(Iteration),
    )
    refs = []
    for object_type, model in (("requirement", Requirement), ("task", Task), ("bug", Bug)):
        filters = [
            model.deleted == 0,
            model.iteration_id.in_(terminal_iteration_ids),
            non_terminal_state_clause(model),
        ]
        if scoped_project_ids is not None:
            filters.append(model.project_id.in_(scoped_project_ids))
        rows = db.query(model.id, model.create_time).filter(*filters).all()
        for item in rows:
            refs.append(
                {
                    "object_type": object_type,
                    "id": item.id,
                    "exception_key": "terminal_iteration_open_item",
                    "exception_label": "已结束迭代存在未完成事项",
                    "entered_at": _datetime_value(item.create_time),
                    "overdue_hours": 0,
                }
            )
    return refs


def _load_workbench_items_by_refs(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    refs: list[dict],
    preserve_duplicates: bool = False,
) -> list[WorkbenchItem]:
    grouped_ids: dict[str, set[int]] = {}
    metadata_by_ref: dict[tuple[str, int], list[dict]] = {}
    for ref in refs:
        object_type = ref["object_type"]
        if object_type not in WORKBENCH_OBJECT_TYPES:
            continue
        grouped_ids.setdefault(object_type, set()).add(ref["id"])
        metadata_by_ref.setdefault((object_type, ref["id"]), []).append(ref)

    items_by_ref: dict[tuple[str, int], WorkbenchItem] = {}
    if grouped_ids.get("requirement"):
        for item in db.query(Requirement).filter(Requirement.deleted == 0, Requirement.id.in_(grouped_ids["requirement"])).all():
            items_by_ref[("requirement", item.id)] = _requirement_item(item, projects, iteration_names)
    if grouped_ids.get("task"):
        for item in db.query(Task).filter(Task.deleted == 0, Task.id.in_(grouped_ids["task"])).all():
            items_by_ref[("task", item.id)] = _task_item(item, projects, iteration_names)
    if grouped_ids.get("bug"):
        for item in db.query(Bug).filter(Bug.deleted == 0, Bug.id.in_(grouped_ids["bug"])).all():
            items_by_ref[("bug", item.id)] = _bug_item(item, projects, iteration_names)
    result: list[WorkbenchItem] = []
    seen: set[tuple[str, int]] = set()
    for ref in refs:
        key = (ref["object_type"], ref["id"])
        if (not preserve_duplicates and key in seen) or key not in items_by_ref:
            continue
        seen.add(key)
        metadata_rows = [ref] if preserve_duplicates else metadata_by_ref[key]
        metadata = {}
        for metadata_row in metadata_rows:
            metadata.update(metadata_row)
        exception_rows = [row for row in metadata_rows if row.get("exception_key")]
        primary_exception = exception_rows[0] if exception_rows else {}
        exception_keys = list(dict.fromkeys(row["exception_key"] for row in exception_rows))
        exception_details = [
            {
                "exception_key": row["exception_key"],
                "exception_label": row.get("exception_label"),
                "exception_detail": row.get("exception_detail"),
                "entered_at": row.get("entered_at"),
            }
            for row in exception_rows
        ]
        item = items_by_ref[key].model_copy(
            update={
                "watch_source": metadata.get("watch_source"),
                "mentioned_in_comment_id": metadata.get("mentioned_in_comment_id"),
                "mentioned_comment_id": metadata.get("mentioned_comment_id"),
                "mentioned_comment_body": metadata.get("mentioned_comment_body"),
                "mentioned_comment_author_id": metadata.get("mentioned_comment_author_id"),
                "mentioned_comment_create_time": metadata.get("mentioned_comment_create_time"),
                "exception_key": primary_exception.get("exception_key"),
                "exception_label": primary_exception.get("exception_label"),
                "exception_keys": exception_keys,
                "exception_details": exception_details,
                "entered_at": primary_exception.get("entered_at"),
                "threshold_hours": primary_exception.get("threshold_hours"),
                "threshold_count": primary_exception.get("threshold_count"),
                "overdue_hours": primary_exception.get("overdue_hours"),
            }
        )
        result.append(item)
    return _sort_workbench_items(result)


def _count_active(db: Session, model) -> int:
    return db.query(func.count(model.id)).filter(model.deleted == 0).scalar() or 0


def _active_iteration_ids(db: Session) -> set[int]:
    return {
        row.id
        for row in (
            db.query(Iteration.id)
            .join(
                WorkflowTransition,
                (WorkflowTransition.definition_id == Iteration.workflow_definition_id)
                & (WorkflowTransition.from_state_id == Iteration.current_state_id),
            )
            .filter(
                Iteration.deleted == 0,
                WorkflowTransition.enabled.is_(True),
                WorkflowTransition.action_key.in_(("complete", "cancel")),
            )
            .distinct()
            .all()
        )
    }


def _in_progress_iteration_ids(db: Session) -> set[int]:
    category_ids = {
        row.id
        for row in db.query(Iteration.id)
        .join(WorkflowState, WorkflowState.id == Iteration.current_state_id)
        .filter(
            Iteration.deleted == 0,
            WorkflowState.category == "in_progress",
        )
        .all()
    }
    normal_start_reached_ids = {
        row.id
        for row in db.query(Iteration.id)
        .join(WorkflowState, WorkflowState.id == Iteration.current_state_id)
        .join(
            WorkflowTransition,
            (WorkflowTransition.definition_id == Iteration.workflow_definition_id)
            & (WorkflowTransition.to_state_id == Iteration.current_state_id),
        )
        .filter(
            Iteration.deleted == 0,
            WorkflowState.category == "normal",
            WorkflowTransition.action_key == "start",
            WorkflowTransition.enabled.is_(True),
        )
        .all()
    }
    return category_ids | normal_start_reached_ids


def _filter_active_scoped_items(
    items: list[WorkbenchItem],
    scoped_project_ids: set[int] | None,
    active_iteration_ids: set[int],
) -> list[WorkbenchItem]:
    return [
        item
        for item in items
        if item.iteration_id in active_iteration_ids
        and _in_project_scope(item.project_id, scoped_project_ids)
    ]


def _review_tasks(db: Session) -> list[dict]:
    tasks = db.query(DevopsCodeReviewTask).order_by(DevopsCodeReviewTask.id.desc()).limit(100).all()
    commit_ids = [item.commit_id for item in tasks]
    commits = {
        item.id: item
        for item in db.query(DevopsCommit).filter(DevopsCommit.id.in_(commit_ids), DevopsCommit.deleted == 0).all()
    } if commit_ids else {}
    link_rows = db.query(DevopsCommitLink).filter(DevopsCommitLink.commit_id.in_(commit_ids)).all() if commit_ids else []
    links: dict[int, list[dict]] = {}
    for row in link_rows:
        links.setdefault(row.commit_id, []).append({"object_type": row.object_type, "object_id": row.object_id})
    result = []
    for task in tasks:
        commit = commits.get(task.commit_id)
        result.append({
            "id": task.id,
            "object_type": "code_review",
            "title": task.title,
            "owner_id": task.owner_id,
            "status": task.status,
            "commit_id": task.commit_id,
            "commit_sha": commit.commit_sha if commit else None,
            "short_sha": commit.short_sha if commit else None,
            "branch_name": commit.branch_name if commit else None,
            "author_name": commit.author_name if commit else None,
            "committed_at": _datetime_value(commit.committed_at) if commit else None,
            "links": links.get(task.commit_id, []),
        })
    return result


def _work_item_reviews(db: Session, user_id: int | None) -> list[dict]:
    if not user_id:
        return []
    rounds = (
        db.query(WorkItemReviewRound)
        .filter(WorkItemReviewRound.reviewer_id == user_id, WorkItemReviewRound.status == "open")
        .order_by(WorkItemReviewRound.update_time.desc(), WorkItemReviewRound.id.desc())
        .all()
    )
    commit_ids = [item.latest_commit_id for item in rounds]
    commits = {
        item.id: item
        for item in db.query(DevopsCommit).filter(DevopsCommit.id.in_(commit_ids), DevopsCommit.deleted == 0).all()
    } if commit_ids else {}
    return [
        {
            "id": item.id,
            "object_type": item.object_type,
            "object_id": item.object_id,
            "latest_commit_id": item.latest_commit_id,
            "reviewer_id": item.reviewer_id,
            "status": item.status,
            "create_time": _datetime_value(item.create_time),
            "update_time": _datetime_value(item.update_time),
            "commit_sha": commits[item.latest_commit_id].commit_sha if item.latest_commit_id in commits else None,
            "short_sha": commits[item.latest_commit_id].short_sha if item.latest_commit_id in commits else None,
        }
        for item in rounds
    ]


def _requirement_item(item: Requirement, projects: dict[int, Project], iteration_names: dict[int, str]) -> WorkbenchItem:
    return WorkbenchItem(
        id=item.id,
        object_type="requirement",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=item.iteration_id,
        iteration_name=_iteration_name(iteration_names, item.iteration_id),
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.owner_id,
        handler_id=item.owner_id,
        iteration_group_key=str(item.iteration_id) if item.iteration_id else "uniterated",
        status=current_state_name(item),
        current_state_id=item.current_state_id,
        status_name=current_state_name(item),
        state_category=item.state_category,
        terminal_kind=getattr(item.current_state, "terminal_kind", None),
        priority=item.priority,
        create_time=_datetime_value(item.create_time),
        update_time=_datetime_value(item.update_time),
        creator_id=item.creator_id,
        requirement_id=item.id,
    )


def _task_item(
    item: Task,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    iteration_id: int | None = None,
) -> WorkbenchItem:
    resolved_iteration_id = iteration_id if iteration_id is not None else item.iteration_id
    return WorkbenchItem(
        id=item.id,
        object_type="task",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=resolved_iteration_id,
        iteration_name=_iteration_name(iteration_names, resolved_iteration_id),
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.owner_id,
        handler_id=item.owner_id,
        iteration_group_key=str(resolved_iteration_id) if resolved_iteration_id else "uniterated",
        status=current_state_name(item),
        current_state_id=item.current_state_id,
        status_name=current_state_name(item),
        state_category=item.state_category,
        terminal_kind=getattr(item.current_state, "terminal_kind", None),
        priority=item.priority,
        due_date=_date_value(item.due_date),
        overdue_hours=_overdue_hours(item.due_date),
        create_time=_datetime_value(item.create_time),
        update_time=_datetime_value(item.update_time),
        creator_id=item.creator_id,
        requirement_id=item.requirement_id,
    )


def _effective_task_iteration_id(db: Session, task: Task) -> int | None:
    if task.iteration_id:
        return task.iteration_id
    if not task.requirement_id:
        return None
    return db.query(Requirement.iteration_id).filter(
        Requirement.id == task.requirement_id,
        Requirement.deleted == 0,
    ).scalar()


def _bug_item(item: Bug, projects: dict[int, Project], iteration_names: dict[int, str]) -> WorkbenchItem:
    return WorkbenchItem(
        id=item.id,
        object_type="bug",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=item.iteration_id,
        iteration_name=_iteration_name(iteration_names, item.iteration_id),
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.owner_id,
        handler_id=item.owner_id,
        iteration_group_key=str(item.iteration_id) if item.iteration_id else "uniterated",
        status=current_state_name(item),
        current_state_id=item.current_state_id,
        status_name=current_state_name(item),
        state_category=item.state_category,
        terminal_kind=getattr(item.current_state, "terminal_kind", None),
        priority=item.priority,
        create_time=_datetime_value(item.create_time),
        update_time=_datetime_value(item.update_time),
        creator_id=item.creator_id,
        requirement_id=item.requirement_id,
        task_id=item.task_id,
        test_case_id=item.test_case_id,
        bug_type=item.bug_type,
        severity=item.severity,
    )


def _project_name(projects: dict[int, Project], project_id: int | None) -> str | None:
    return projects.get(project_id).name if project_id in projects else None


def _iteration_name(iteration_names: dict[int, str], iteration_id: int | None) -> str | None:
    return iteration_names.get(iteration_id) if iteration_id else None


def _date_value(value) -> str | None:
    return value.isoformat() if value else None


def _overdue_hours(due_date) -> float | None:
    if not due_date:
        return None
    due_at = datetime.combine(due_date, time.max)
    return round(max(0.0, (datetime.now() - due_at).total_seconds() / 3600), 2)


def _datetime_value(value) -> str | None:
    return value.isoformat() if value else None


def _in_project_scope(project_id: int | None, scoped_project_ids: set[int] | None) -> bool:
    if scoped_project_ids is None:
        return True
    return bool(project_id and project_id in scoped_project_ids)


def _sort_workbench_items(items: list[WorkbenchItem]) -> list[WorkbenchItem]:
    return sorted(items, key=lambda item: (item.create_time or "", item.id), reverse=True)


def _dedup_and_sort_workbench_items(items: list[WorkbenchItem]) -> list[WorkbenchItem]:
    deduped: dict[tuple[str, int], WorkbenchItem] = {}
    for item in items:
        deduped[(item.object_type, item.id)] = item
    return _sort_workbench_items(list(deduped.values()))


def _role_ids_for_user(db: Session, user_id: int | None, project_ids: set[int]) -> list[int]:
    if not user_id:
        return []
    if not project_ids:
        return []
    return sorted({
        role_id
        for (role_id,) in db.query(ProjectMember.role_id)
        .filter(ProjectMember.user_id == user_id, ProjectMember.project_id.in_(project_ids), ProjectMember.role_id.isnot(None))
        .all()
    })


def _workbench_view_mode(db: Session, user_id: int | None, role_ids: list[int]) -> str:
    if is_system_admin(db, user_id):
        return "all"
    lead_role_ids = role_ids_for_capabilities(db, {"project_owner", "product_manager", "development_lead"})
    if set(role_ids) & lead_role_ids:
        return "lead"
    return "mine"
def _filter_review_tasks_for_role(review_tasks: list[dict], user_id: int | None, view_mode: str) -> list[dict]:
    if view_mode in {"all", "lead"} or not user_id:
        return review_tasks
    if view_mode == "developer":
        return [item for item in review_tasks if item.get("owner_id") == user_id]
    return []
