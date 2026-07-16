from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.devops import DevopsCodeReviewTask, DevopsCommit, DevopsCommitLink
from app.models.iteration import Iteration
from app.models.object_watch import ObjectWatch
from app.models.program import Program
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.user import User
from app.models.work_item_comment import WorkItemComment
from app.services.exception_center_service import list_exception_refs
from app.services.project_team_service import workbench_project_ids_for_user
from app.services.workflow_state_query_service import current_state_name, is_terminal_state, non_terminal_state_clause
from app.views.dashboard_view import (
    DashboardSummary,
    WorkbenchItem,
    WorkbenchResponse,
    WorkbenchSection,
)


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
    role_keys = _role_keys_for_user(db, user_id)
    view_mode = _workbench_view_mode(role_keys)
    team_project_ids = workbench_project_ids_for_user(db, user_id) if user_id else set()
    scoped_project_ids = _expand_project_scope_ids(db, team_project_ids) if team_project_ids else set()
    projects = {item.id: item for item in db.query(Project).filter(Project.deleted == 0).all()}
    iteration_names = {item.id: item.name for item in db.query(Iteration).filter(Iteration.deleted == 0).all()}
    queue_scope_ids = scoped_project_ids if user_id and view_mode != "all" else set()
    pending_items = _pending_handling_items(db, projects, iteration_names, user_id, queue_scope_ids)
    unassigned_items = _unassigned_items(db, projects, iteration_names, queue_scope_ids)
    created_items = _created_by_me_items(db, projects, iteration_names, user_id)
    watched_items = _watched_by_me_items(db, projects, iteration_names, user_id)
    mentioned_items = _mentioned_me_items(db, projects, iteration_names, user_id)
    exception_items = _exception_center_items(db, projects, iteration_names, queue_scope_ids)
    review_tasks = _filter_review_tasks_for_role(_review_tasks(db), user_id, view_mode)
    owner_ids = {
        item.owner_id
        for section in [pending_items, unassigned_items, created_items, watched_items, mentioned_items, exception_items]
        for item in section
        if item.owner_id
    }
    owner_ids.update(item.get("owner_id") for item in review_tasks if item.get("owner_id"))
    owners = [
        {"id": user.id, "full_name": user.full_name}
        for user in db.query(User).filter(User.deleted == 0, User.id.in_(owner_ids)).order_by(User.full_name.asc()).all()
    ] if owner_ids else []
    return WorkbenchResponse(
        pending_handling=WorkbenchSection(label="待处理", items=pending_items, total=len(pending_items)),
        unassigned=WorkbenchSection(label="未分派", items=unassigned_items, total=len(unassigned_items)),
        created_by_me=WorkbenchSection(label="我发起的", items=created_items, total=len(created_items)),
        watched_by_me=WorkbenchSection(label="我关注的", items=watched_items, total=len(watched_items)),
        mentioned_me=WorkbenchSection(label="提到我的", items=mentioned_items, total=len(mentioned_items)),
        exception_center=WorkbenchSection(label="异常中心", items=exception_items, total=len(exception_items)),
        owners=owners,
        review_tasks=review_tasks,
        role_keys=role_keys,
        view_mode=view_mode,
    )
def _pending_handling_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    user_id: int | None,
    scoped_project_ids: set[int],
) -> list[WorkbenchItem]:
    if not user_id:
        return []
    items = [
        _requirement_item(item, projects, iteration_names)
        for item in db.query(Requirement).filter(Requirement.deleted == 0, Requirement.owner_id == user_id).all()
        if not is_terminal_state(item) and _in_project_scope(item.project_id, scoped_project_ids)
    ]
    items.extend(
        _task_item(item, projects, iteration_names)
        for item in db.query(Task).filter(Task.deleted == 0, Task.owner_id == user_id).all()
        if not is_terminal_state(item) and _in_project_scope(item.project_id, scoped_project_ids)
    )
    items.extend(
        _bug_item(item, projects, iteration_names)
        for item in db.query(Bug).filter(Bug.deleted == 0, Bug.owner_id == user_id).all()
        if not is_terminal_state(item) and _in_project_scope(item.project_id, scoped_project_ids)
    )
    items.extend(
        _test_case_item(item, projects, iteration_names)
        for item in db.query(TestCase).filter(TestCase.deleted == 0, TestCase.default_tester_id == user_id).all()
        if _in_project_scope(item.project_id, scoped_project_ids)
    )
    return _sort_workbench_items(items)


def _unassigned_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    scoped_project_ids: set[int],
) -> list[WorkbenchItem]:
    items = [
        _requirement_item(item, projects, iteration_names)
        for item in db.query(Requirement).filter(Requirement.deleted == 0, Requirement.owner_id.is_(None)).all()
        if not is_terminal_state(item) and _in_project_scope(item.project_id, scoped_project_ids)
    ]
    items.extend(
        _task_item(item, projects, iteration_names)
        for item in db.query(Task).filter(Task.deleted == 0, Task.owner_id.is_(None)).all()
        if not is_terminal_state(item) and _in_project_scope(item.project_id, scoped_project_ids)
    )
    items.extend(
        _bug_item(item, projects, iteration_names)
        for item in db.query(Bug).filter(Bug.deleted == 0, Bug.owner_id.is_(None)).all()
        if not is_terminal_state(item) and _in_project_scope(item.project_id, scoped_project_ids)
    )
    return _sort_workbench_items(items)


def _created_by_me_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    user_id: int | None,
) -> list[WorkbenchItem]:
    if not user_id:
        return []
    items = [
        _requirement_item(item, projects, iteration_names)
        for item in db.query(Requirement).filter(Requirement.deleted == 0).all()
        if item.creator_id == user_id or item.proposer_id == user_id
    ]
    items.extend(
        _task_item(item, projects, iteration_names)
        for item in db.query(Task).filter(Task.deleted == 0, Task.creator_id == user_id).all()
    )
    items.extend(
        _bug_item(item, projects, iteration_names)
        for item in db.query(Bug).filter(Bug.deleted == 0).all()
        if item.creator_id == user_id or item.reporter_id == user_id
    )
    items.extend(
        _test_case_item(item, projects, iteration_names)
        for item in db.query(TestCase).filter(TestCase.deleted == 0, TestCase.creator_id == user_id).all()
    )
    items.extend(
        _test_run_item(item, projects, iteration_names)
        for item in db.query(TestRun).filter(TestRun.deleted == 0, TestRun.creator_id == user_id).all()
    )
    return _dedup_and_sort_workbench_items(items)


def _watched_by_me_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    user_id: int | None,
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
    return _load_workbench_items_by_refs(db, projects, iteration_names, refs)


def _mentioned_me_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    user_id: int | None,
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
            }
        )
    return _load_workbench_items_by_refs(db, projects, iteration_names, refs)


def _exception_center_items(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    scoped_project_ids: set[int],
) -> list[WorkbenchItem]:
    refs = list_exception_refs(db, scoped_project_ids if scoped_project_ids else None)
    return _load_workbench_items_by_refs(db, projects, iteration_names, refs)


def _load_workbench_items_by_refs(
    db: Session,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    refs: list[dict],
) -> list[WorkbenchItem]:
    grouped_ids: dict[str, set[int]] = {}
    metadata_by_ref: dict[tuple[str, int], dict] = {}
    for ref in refs:
        object_type = ref["object_type"]
        grouped_ids.setdefault(object_type, set()).add(ref["id"])
        metadata_by_ref.setdefault((object_type, ref["id"]), {}).update(ref)

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
    if grouped_ids.get("test_case"):
        for item in db.query(TestCase).filter(TestCase.deleted == 0, TestCase.id.in_(grouped_ids["test_case"])).all():
            items_by_ref[("test_case", item.id)] = _test_case_item(item, projects, iteration_names)
    if grouped_ids.get("test_run"):
        for item in db.query(TestRun).filter(TestRun.deleted == 0, TestRun.id.in_(grouped_ids["test_run"])).all():
            items_by_ref[("test_run", item.id)] = _test_run_item(item, projects, iteration_names)

    result: list[WorkbenchItem] = []
    seen: set[tuple[str, int]] = set()
    for ref in refs:
        key = (ref["object_type"], ref["id"])
        if key in seen or key not in items_by_ref:
            continue
        seen.add(key)
        item = items_by_ref[key].model_copy(
            update={
                "watch_source": metadata_by_ref[key].get("watch_source"),
                "mentioned_in_comment_id": metadata_by_ref[key].get("mentioned_in_comment_id"),
                "exception_key": metadata_by_ref[key].get("exception_key"),
                "exception_label": metadata_by_ref[key].get("exception_label"),
                "entered_at": metadata_by_ref[key].get("entered_at"),
                "threshold_hours": metadata_by_ref[key].get("threshold_hours"),
                "threshold_count": metadata_by_ref[key].get("threshold_count"),
                "overdue_hours": metadata_by_ref[key].get("overdue_hours"),
            }
        )
        result.append(item)
    return _sort_workbench_items(result)


def _count_active(db: Session, model) -> int:
    return db.query(func.count(model.id)).filter(model.deleted == 0).scalar() or 0


def _expand_project_scope_ids(db: Session, project_ids: set[int]) -> set[int]:
    expanded = set(project_ids)
    for project_id in project_ids:
        expanded.update(_collect_descendant_project_ids(db, project_id))
        expanded.update(_collect_ancestor_project_ids(db, project_id))
    return expanded


def _collect_descendant_project_ids(db: Session, project_id: int) -> set[int]:
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    result = {child.id for child in children}
    for child in children:
        result.update(_collect_descendant_project_ids(db, child.id))
    return result


def _collect_ancestor_project_ids(db: Session, project_id: int) -> set[int]:
    result = set()
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    parent_id = project.parent_id if project else None
    visited = set()
    while parent_id and parent_id not in visited:
        visited.add(parent_id)
        parent = db.query(Project).filter(Project.id == parent_id, Project.deleted == 0).first()
        if not parent:
            break
        result.add(parent.id)
        parent_id = parent.parent_id
    return result


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
        priority=item.priority,
        create_time=_datetime_value(item.create_time),
        creator_id=item.creator_id,
        proposer_id=item.proposer_id,
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
        priority=item.priority,
        due_date=_date_value(item.due_date),
        create_time=_datetime_value(item.create_time),
        creator_id=item.creator_id,
        requirement_id=item.requirement_id,
    )


def _test_case_item(
    item: TestCase,
    projects: dict[int, Project],
    iteration_names: dict[int, str],
    iteration_id: int | None = None,
) -> WorkbenchItem:
    resolved_iteration_id = iteration_id if iteration_id is not None else item.iteration_id
    return WorkbenchItem(
        id=item.id,
        object_type="test_case",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=resolved_iteration_id,
        iteration_name=_iteration_name(iteration_names, resolved_iteration_id),
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.default_tester_id,
        handler_id=item.default_tester_id,
        iteration_group_key=str(resolved_iteration_id) if resolved_iteration_id else "uniterated",
        status=item.status,
        create_time=_datetime_value(item.create_time),
        creator_id=item.creator_id,
        last_execute_time=_datetime_value(item.last_execute_time),
        last_execute_result=item.last_execute_result,
        steps_json=item.steps_json,
        requirement_id=item.requirement_id,
        test_case_id=item.id,
    )


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
        priority=item.priority,
        create_time=_datetime_value(item.create_time),
        creator_id=item.creator_id,
        reporter_id=item.reporter_id,
        requirement_id=item.requirement_id,
        task_id=item.task_id,
        test_case_id=item.test_case_id,
        bug_type=item.bug_type,
        severity=item.severity,
    )


def _test_run_item(item: TestRun, projects: dict[int, Project], iteration_names: dict[int, str]) -> WorkbenchItem:
    return WorkbenchItem(
        id=item.id,
        object_type="test_run",
        title=item.name,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=item.iteration_id,
        iteration_name=_iteration_name(iteration_names, item.iteration_id),
        iteration_group_key=str(item.iteration_id) if item.iteration_id else "uniterated",
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.test_owner_id,
        handler_id=item.test_owner_id,
        status=item.status,
        create_time=_datetime_value(item.create_time),
        creator_id=item.creator_id,
    )


def _project_name(projects: dict[int, Project], project_id: int | None) -> str | None:
    return projects.get(project_id).name if project_id in projects else None


def _iteration_name(iteration_names: dict[int, str], iteration_id: int | None) -> str | None:
    return iteration_names.get(iteration_id) if iteration_id else None


def _date_value(value) -> str | None:
    return value.isoformat() if value else None


def _datetime_value(value) -> str | None:
    return value.isoformat() if value else None


def _in_project_scope(project_id: int | None, scoped_project_ids: set[int] | None) -> bool:
    if not scoped_project_ids:
        return True
    return bool(project_id and project_id in scoped_project_ids)


def _sort_workbench_items(items: list[WorkbenchItem]) -> list[WorkbenchItem]:
    return sorted(items, key=lambda item: (item.create_time or "", item.id), reverse=True)


def _dedup_and_sort_workbench_items(items: list[WorkbenchItem]) -> list[WorkbenchItem]:
    deduped: dict[tuple[str, int], WorkbenchItem] = {}
    for item in items:
        deduped[(item.object_type, item.id)] = item
    return _sort_workbench_items(list(deduped.values()))


def _role_keys_for_user(db: Session, user_id: int | None) -> list[str]:
    if not user_id:
        return []
    rows = (
        db.query(Role.role_key)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id, Role.enabled.is_(True))
        .order_by(Role.id.asc())
        .all()
    )
    return [row.role_key for row in rows]


def _workbench_view_mode(role_keys: list[str]) -> str:
    role_set = set(role_keys)
    if "system_admin" in role_set:
        return "all"
    if role_set & {"project_owner", "product_manager", "development_lead"}:
        return "lead"
    return "mine"
def _filter_review_tasks_for_role(review_tasks: list[dict], user_id: int | None, view_mode: str) -> list[dict]:
    if view_mode in {"all", "lead"} or not user_id:
        return review_tasks
    if view_mode == "developer":
        return [item for item in review_tasks if item.get("owner_id") == user_id]
    return []
