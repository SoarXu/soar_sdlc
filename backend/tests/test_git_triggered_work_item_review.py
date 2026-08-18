from uuid import uuid4

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.devops import WorkItemReviewRound
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User
from app.models.workflow_definition import WorkflowTransition
from app.services.iteration_assignment_service import create_unstarted_iteration
from app.services.workflow_state_service import initial_system_workflow_values, initial_workflow_values


def _user(db, role_key: str) -> User:
    role = db.query(Role).filter(Role.role_key == role_key).first()
    if not role:
        role = Role(role_key=role_key, role_name=role_key, enabled=True, is_system=True)
        db.add(role)
        db.flush()
    user = User(
        username=f"git_review_{role_key}_{uuid4().hex[:8]}",
        full_name=f"Git Review {role_key}",
        password_hash=get_password_hash("User123456"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    return user


def _move_to_development_state(db, object_type: str, item) -> None:
    transition = (
        db.query(WorkflowTransition)
        .filter(
            WorkflowTransition.definition_id == item.workflow_definition_id,
            WorkflowTransition.action_key == "submit_review",
        )
        .first()
    )
    assert transition is not None
    item.current_state_id = transition.from_state_id


def test_linked_git_commits_open_and_update_one_review_round_per_development_work_item(client):
    db = SessionLocal()
    try:
        developer = _user(db, "developer")
        lead = _user(db, "development_lead")
        project = Project(name=f"Git review project {uuid4().hex[:8]}", **initial_system_workflow_values(db, "project"))
        db.add(project)
        db.flush()
        iteration = create_unstarted_iteration(db, project.id)
        db.commit()
        started = client.post(
            f"/api/v1/workflow-runtime/iteration/{iteration.id}/transition",
            json={"action_key": "start", "payload": {"effective_time": "2026-08-19T09:00:00"}},
        )
        assert started.status_code == 200, started.text
        requirement = Requirement(
            project_id=project.id,
            iteration_id=iteration.id,
            title="Git review requirement",
            owner_id=developer.id,
            **initial_workflow_values(db, "requirement", project.id),
        )
        db.add(requirement)
        db.flush()
        task = Task(
            project_id=project.id,
            iteration_id=iteration.id,
            requirement_id=requirement.id,
            title="Git review task",
            owner_id=developer.id,
            **initial_workflow_values(db, "task", project.id),
        )
        bug = Bug(
            project_id=project.id,
            iteration_id=iteration.id,
            requirement_id=requirement.id,
            title="Git review bug",
            owner_id=developer.id,
            **initial_workflow_values(db, "bug", project.id),
        )
        db.add_all([task, bug])
        db.flush()
        for object_type, item in (("requirement", requirement), ("task", task), ("bug", bug)):
            _move_to_development_state(db, object_type, item)
        db.commit()

        first = client.post(
            "/api/v1/devops/commits",
            json={
                "commit_sha": f"first{uuid4().hex}",
                "message": f"REQ-{requirement.id} TASK-{task.id} BUG-{bug.id} implement review gate",
                "diff_text": "diff --git a/review.md b/review.md\n+first change",
            },
        )
        assert first.status_code == 201, first.text
        first_id = first.json()["id"]
        first_detail = client.get(f"/api/v1/devops/commits/{first_id}").json()
        assert {(link["object_type"], link["object_id"]) for link in first_detail["links"]} == {
            ("requirement", requirement.id),
            ("task", task.id),
            ("bug", bug.id),
        }
        assert client.get(f"/api/v1/requirements/{requirement.id}").json()["status_name"] == "待评审"

        db.rollback()
        rounds = db.query(WorkItemReviewRound).filter(WorkItemReviewRound.status == "open").all()
        assert {(round.object_type, round.object_id) for round in rounds} == {
            ("requirement", requirement.id),
            ("task", task.id),
            ("bug", bug.id),
        }
        development_lead_ids = {
            user_id
            for (user_id,) in db.query(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(Role.role_key == "development_lead", Role.enabled.is_(True))
            .all()
        }
        assert {round.reviewer_id for round in rounds} <= development_lead_ids
        assert {round.latest_commit_id for round in rounds} == {first_id}

        second = client.post(
            "/api/v1/devops/commits",
            json={
                "commit_sha": f"second{uuid4().hex}",
                "message": f"TASK-{task.id} follow-up fix",
                "diff_text": "diff --git a/review.md b/review.md\n+second change",
            },
        )
        assert second.status_code == 201, second.text
        retry = client.post(
            "/api/v1/devops/commits",
            json={
                "commit_sha": second.json()["commit_sha"],
                "message": f"TASK-{task.id} follow-up fix",
                "diff_text": "diff --git a/review.md b/review.md\nsecond change",
            },
        )
        assert retry.status_code == 201, retry.text

        db.rollback()
        task_rounds = db.query(WorkItemReviewRound).filter(
            WorkItemReviewRound.object_type == "task",
            WorkItemReviewRound.object_id == task.id,
        ).all()
        assert len(task_rounds) == 1
        assert task_rounds[0].latest_commit_id == second.json()["id"]
    finally:
        db.close()
