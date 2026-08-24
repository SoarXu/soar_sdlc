from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.task import Task
from app.services.workflow_state_query_service import is_terminal_state


def get_locked_active_task(db: Session, task_id: int) -> Task:
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.deleted == 0)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent task not found")
    return task


def validate_child_parent(parent: Task) -> None:
    if is_terminal_state(parent):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TASK_PARENT_TERMINAL",
                "message": "Cannot create a child task under a completed or canceled task",
                "parent_task_id": parent.id,
            },
        )


def list_direct_children(db: Session, task_id: int, *, for_update: bool = False) -> list[Task]:
    query = (
        db.query(Task)
        .filter(Task.parent_task_id == task_id, Task.deleted == 0)
        .order_by(Task.id.asc())
    )
    if for_update:
        query = query.with_for_update().populate_existing()
    return query.all()


def list_descendants(db: Session, task_id: int, *, for_update: bool = False) -> list[Task]:
    descendants: list[Task] = []
    pending_parent_ids = [task_id]
    visited_ids = {task_id}

    while pending_parent_ids:
        query = (
            db.query(Task)
            .filter(Task.parent_task_id.in_(pending_parent_ids), Task.deleted == 0)
            .order_by(Task.id.asc())
        )
        if for_update:
            query = query.with_for_update().populate_existing()
        level = [task for task in query.all() if task.id not in visited_ids]
        if not level:
            break
        descendants.extend(level)
        visited_ids.update(task.id for task in level)
        pending_parent_ids = [task.id for task in level]

    return descendants


def task_tree(db: Session, root: Task, *, for_update: bool = False) -> list[Task]:
    if for_update:
        root = get_locked_active_task(db, root.id)
    return [root, *list_descendants(db, root.id, for_update=for_update)]


def synchronize_task_tree_scope(
    db: Session,
    root: Task,
    *,
    project_id: int,
    requirement_id: int | None,
    iteration_id: int | None,
    actor_id: int | None,
    reason: str,
) -> list[Task]:
    """Move a root task and every active descendant in one caller-owned transaction."""
    from app.services.iteration_service import ensure_iteration_assignment_mutable
    from app.services.work_item_iteration_history_service import move_work_item_to_iteration

    root = get_locked_active_task(db, root.id)
    if root.parent_task_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CHILD_TASK_SCOPE_IMMUTABLE",
                "message": "子任务的项目、需求和迭代由父任务统一管理。",
            },
        )
    tasks = [root, *list_descendants(db, root.id, for_update=True)]
    terminal_tasks = [task for task in tasks if is_terminal_state(task)]
    if terminal_tasks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TASK_TREE_MOVE_BLOCKED",
                "message": "任务树中存在已结束任务，无法整体调整归属。",
                "blockers": [
                    {
                        "id": task.id,
                        "title": task.title,
                        "status_name": task.status_name,
                        "parent_task_id": task.parent_task_id,
                    }
                    for task in terminal_tasks
                ],
            },
        )
    for task in tasks:
        ensure_iteration_assignment_mutable(db, task.iteration_id, iteration_id)
    for task in tasks:
        move_work_item_to_iteration(
            db,
            task,
            iteration_id,
            actor_id=actor_id,
            reason=reason,
        )
        task.project_id = project_id
        task.requirement_id = requirement_id
    return tasks
