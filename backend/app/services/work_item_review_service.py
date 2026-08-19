from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.devops import DevopsCommit, DevopsCommitLink, WorkItemReviewRound
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.user import User
from app.models.workflow_definition import WorkflowTransition
from app.services.project_permission_service import actor_role_keys
from app.services import workflow_runtime_service
from app.views.workflow_runtime_view import WorkflowTransitionExecuteRequest


MODEL_BY_TYPE = {"requirement": Requirement, "task": Task, "bug": Bug}
DEVELOPMENT_STATE_NAMES = {"处理中", "修复中"}


def trigger_linked_work_item_reviews(
    db: Session,
    commit: DevopsCommit,
    links: list[dict[str, int | str]],
) -> list[WorkItemReviewRound]:
    result = []
    for link in links:
        object_type = str(link["object_type"])
        object_id = int(link["object_id"])
        item = _get_item(db, object_type, object_id)
        if not item:
            continue
        actor = _transition_actor(db, item)
        if actor is None:
            continue
        try:
            result.append(submit_work_item_review(db, object_type, object_id, actor, commit=commit))
        except HTTPException:
            continue
    return result


def submit_work_item_review(
    db: Session,
    object_type: str,
    object_id: int,
    actor: User | None,
    *,
    commit: DevopsCommit | None = None,
) -> WorkItemReviewRound:
    item = _get_item(db, object_type, object_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到工作项")
    active_round = _active_round(db, object_type, object_id)
    if active_round:
        if commit is not None:
            active_round.latest_commit_id = commit.id
            db.flush()
        return active_round

    transition = _submit_review_transition(db, item)
    if not transition:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前状态不可提交评审")
    reviewer_id = _development_lead_user_id(db, getattr(item, "project_id", None))
    if reviewer_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="未找到可用的研发负责人进行评审")
    workflow_runtime_service._execute_transition(
        db,
        object_type,
        item,
        WorkflowTransitionExecuteRequest(transition_id=transition.id),
        actor,
        commit=False,
        allow_system_action=True,
    )
    review_round = WorkItemReviewRound(
        object_type=object_type,
        object_id=object_id,
        latest_commit_id=commit.id if commit else None,
        reviewer_id=reviewer_id,
        status="open",
        active_key="open",
    )
    db.add(review_round)
    db.flush()
    return review_round


def decide_review_round(
    db: Session,
    review_round_id: int,
    decision: str,
    remark: str | None,
    actor: User | None,
) -> WorkItemReviewRound:
    review_round = db.query(WorkItemReviewRound).filter(WorkItemReviewRound.id == review_round_id).with_for_update().first()
    if not review_round:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到工作项评审记录")
    if review_round.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该工作项评审已完成")
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不支持的评审决定")
    if decision == "reject" and not (remark or "").strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="评审不通过时必须填写原因")

    item = _get_item(db, review_round.object_type, review_round.object_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到被评审的工作项")
    if not _is_assigned_development_lead(db, item, review_round, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅指定的开发主管可以进行代码评审")
    action_key = "approve_review" if decision == "approve" else "reject_review"
    transition = (
        db.query(WorkflowTransition)
        .filter(
            WorkflowTransition.definition_id == item.workflow_definition_id,
            WorkflowTransition.from_state_id == item.current_state_id,
            WorkflowTransition.action_key == action_key,
            WorkflowTransition.enabled.is_(True),
        )
        .first()
    )
    if not transition:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前状态不可执行评审流转")
    workflow_runtime_service._execute_transition(
        db,
        review_round.object_type,
        item,
        WorkflowTransitionExecuteRequest(transition_id=transition.id, payload={"reason": remark} if remark else {}),
        actor,
        commit=False,
    )
    review_round.status = "approved" if decision == "approve" else "rejected"
    review_round.active_key = None
    review_round.decision_by_id = actor.id
    review_round.decision_at = datetime.now()
    review_round.remark = remark
    db.commit()
    db.refresh(review_round)
    return review_round


def get_review_context(
    db: Session,
    object_type: str,
    object_id: int,
    actor: User | None,
) -> dict:
    review_round = _open_round(db, object_type, object_id)
    if not review_round:
        item = _get_item(db, object_type, object_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到待评审的工作项")
        if not _is_project_development_lead(db, item, actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅开发主管可以查看代码评审")
        if not _has_review_decisions(db, item):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到待评审的工作项")
        review_round = WorkItemReviewRound(
            object_type=object_type,
            object_id=object_id,
            latest_commit_id=_latest_linked_commit_id(db, object_type, object_id),
            reviewer_id=actor.id,
            status="open",
            active_key="open",
        )
        db.add(review_round)
        db.commit()
        db.refresh(review_round)
    else:
        item = _get_item(db, object_type, object_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到被评审的工作项")
        if not _is_assigned_development_lead(db, item, review_round, actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅指定的开发主管可以查看代码评审")

    commit = None
    if review_round.latest_commit_id:
        commit = (
            db.query(DevopsCommit)
            .filter(DevopsCommit.id == review_round.latest_commit_id, DevopsCommit.deleted == 0)
            .first()
        )
    diff_text = commit.diff_text if commit else None
    diff_json = commit.diff_json if commit else None
    return {
        "review_round": review_round,
        "commit": commit,
        "diff_text": diff_text,
        "diff_json": diff_json,
        "has_diff": bool((diff_text or "").strip() or diff_json),
    }


def list_open_review_rounds(db: Session, reviewer_id: int) -> list[WorkItemReviewRound]:
    return (
        db.query(WorkItemReviewRound)
        .filter(
            WorkItemReviewRound.reviewer_id == reviewer_id,
            WorkItemReviewRound.status == "open",
        )
        .order_by(WorkItemReviewRound.update_time.desc(), WorkItemReviewRound.id.desc())
        .all()
    )


def _get_item(db: Session, object_type: str, object_id: int):
    model = MODEL_BY_TYPE.get(object_type)
    if not model:
        return None
    return db.query(model).filter(model.id == object_id, model.deleted == 0).with_for_update().first()


def _active_round(db: Session, object_type: str, object_id: int) -> WorkItemReviewRound | None:
    return (
        db.query(WorkItemReviewRound)
        .filter(
            WorkItemReviewRound.object_type == object_type,
            WorkItemReviewRound.object_id == object_id,
            WorkItemReviewRound.status == "open",
        )
        .with_for_update()
        .first()
    )


def _open_round(db: Session, object_type: str, object_id: int) -> WorkItemReviewRound | None:
    return (
        db.query(WorkItemReviewRound)
        .filter(
            WorkItemReviewRound.object_type == object_type,
            WorkItemReviewRound.object_id == object_id,
            WorkItemReviewRound.status == "open",
        )
        .first()
    )


def _submit_review_transition(db: Session, item) -> WorkflowTransition | None:
    transition = (
        db.query(WorkflowTransition)
        .filter(
            WorkflowTransition.definition_id == item.workflow_definition_id,
            WorkflowTransition.from_state_id == item.current_state_id,
            WorkflowTransition.action_key == "submit_review",
            WorkflowTransition.enabled.is_(True),
        )
        .first()
    )
    return transition


def _transition_actor(db: Session, item) -> User | None:
    owner_id = getattr(item, "owner_id", None)
    if not owner_id:
        return None
    return db.query(User).filter(User.id == owner_id, User.deleted == 0, User.is_active.is_(True)).first()


def _development_lead_user_id(db: Session, project_id: int | None = None) -> int | None:
    if project_id:
        row = (
            db.query(User.id)
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.project_role == "development_lead",
                User.deleted == 0,
                User.is_active.is_(True),
            )
            .order_by(User.id.asc())
            .first()
        )
        if row:
            return row.id
    return None


def _is_project_development_lead(db: Session, item, actor: User | None) -> bool:
    return bool(
        actor
        and "development_lead" in actor_role_keys(db, getattr(item, "project_id", None), actor.id)
    )


def _is_assigned_development_lead(db: Session, item, review_round: WorkItemReviewRound, actor: User | None) -> bool:
    return bool(actor and actor.id == review_round.reviewer_id and _is_project_development_lead(db, item, actor))


def _has_review_decisions(db: Session, item) -> bool:
    action_keys = {
        row.action_key
        for row in db.query(WorkflowTransition.action_key)
        .filter(
            WorkflowTransition.definition_id == item.workflow_definition_id,
            WorkflowTransition.from_state_id == item.current_state_id,
            WorkflowTransition.action_key.in_({"approve_review", "reject_review"}),
            WorkflowTransition.enabled.is_(True),
        )
        .all()
    }
    return action_keys == {"approve_review", "reject_review"}


def _latest_linked_commit_id(db: Session, object_type: str, object_id: int) -> int | None:
    row = (
        db.query(DevopsCommit.id)
        .join(DevopsCommitLink, DevopsCommitLink.commit_id == DevopsCommit.id)
        .filter(
            DevopsCommitLink.object_type == object_type,
            DevopsCommitLink.object_id == object_id,
            DevopsCommit.deleted == 0,
        )
        .order_by(DevopsCommit.committed_at.desc(), DevopsCommit.id.desc())
        .first()
    )
    return row.id if row else None
