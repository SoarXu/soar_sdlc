from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.security import get_password_hash
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.devops import DevopsCommit, WorkItemReviewRound
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.user import User
from app.models.workflow_definition import WorkflowTransition
from app.services.iteration_assignment_service import create_unstarted_iteration
from app.services.work_item_review_service import decide_review_round, submit_work_item_review
from app.services.workflow_state_service import initial_system_workflow_values, initial_workflow_values


def _user(db, role_key: str) -> User:
    role = db.query(Role).filter(Role.role_key == role_key).first()
    if not role:
        role = Role(role_key=role_key, role_name=role_key, enabled=True, is_system=True)
        db.add(role)
        db.flush()
    user = User(
        username=f"review_decision_{uuid4().hex[:8]}",
        full_name=role_key,
        password_hash=get_password_hash("User123456"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    return user


def test_review_round_decision_enforces_reviewer_and_records_workflow_audit():
    db = SessionLocal()
    try:
        developer = _user(db, "developer")
        lead = _user(db, "development_lead")
        outsider = _user(db, "developer")
        project = Project(name=f"Review decision {uuid4().hex[:8]}", **initial_system_workflow_values(db, "project"))
        db.add(project)
        db.flush()
        iteration = create_unstarted_iteration(db, project.id)
        requirement = Requirement(
            project_id=project.id,
            iteration_id=iteration.id,
            title="Review decision requirement",
            owner_id=developer.id,
            **initial_workflow_values(db, "requirement", project.id),
        )
        db.add(requirement)
        db.flush()
        submit = db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == requirement.workflow_definition_id,
            WorkflowTransition.action_key == "submit_review",
        ).first()
        requirement.current_state_id = submit.to_state_id
        commit = DevopsCommit(provider="gitea", commit_sha=f"review{uuid4().hex}")
        db.add(commit)
        db.flush()
        review_round = WorkItemReviewRound(
            object_type="requirement",
            object_id=requirement.id,
            latest_commit_id=commit.id,
            reviewer_id=lead.id,
            status="open",
            active_key="open",
        )
        db.add(review_round)
        db.commit()

        with pytest.raises(HTTPException, match="仅指定的开发主管可以进行代码评审"):
            decide_review_round(db, review_round.id, "approve", None, outsider)

        result = decide_review_round(db, review_round.id, "approve", None, lead)
        assert result.status == "approved"
        assert result.active_key is None
        assert result.decision_by_id == lead.id
        approved_transition = db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == requirement.workflow_definition_id,
            WorkflowTransition.action_key == "approve_review",
        ).first()
        assert db.query(Requirement).filter(Requirement.id == requirement.id).one().current_state_id == approved_transition.to_state_id
    finally:
        db.close()


def test_manual_review_submission_creates_commitless_round_then_auto_submission_updates_it(client):
    db = SessionLocal()
    try:
        developer = _user(db, "developer")
        lead = _user(db, "development_lead")
        project = Project(name=f"Manual review {uuid4().hex[:8]}", **initial_system_workflow_values(db, "project"))
        db.add(project)
        db.flush()
        iteration = create_unstarted_iteration(db, project.id)
        requirement = Requirement(
            project_id=project.id,
            iteration_id=iteration.id,
            title="Manual review requirement",
            owner_id=developer.id,
            **initial_workflow_values(db, "requirement", project.id),
        )
        db.add(requirement)
        db.flush()
        submit = db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == requirement.workflow_definition_id,
            WorkflowTransition.action_key == "submit_review",
        ).one()
        requirement.current_state_id = submit.from_state_id
        db.commit()

        submitted = client.post(
            f"/api/v1/devops/work-item-reviews/requirement/{requirement.id}/submit",
            headers={"Authorization": f"Bearer {create_access_token(developer.username)}"},
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["latest_commit_id"] is None
        db.rollback()
        manual_round = db.query(WorkItemReviewRound).filter(WorkItemReviewRound.id == submitted.json()["id"]).one()
        assert manual_round.status == "open"
        assert db.query(Requirement).filter(Requirement.id == requirement.id).one().current_state_id == submit.to_state_id

        context = client.get(
            f"/api/v1/devops/work-item-reviews/requirement/{requirement.id}/context",
            headers={"Authorization": f"Bearer {create_access_token(lead.username)}"},
        )
        assert context.status_code == 200, context.text
        assert context.json()["review_round"]["id"] == manual_round.id
        assert context.json()["commit"] is None
        assert context.json()["has_diff"] is False
        assert context.json()["diff_text"] is None

        commit = DevopsCommit(
            provider="gitea",
            commit_sha=f"manual-follow-up{uuid4().hex}",
            diff_text="diff --git a/review.txt b/review.txt\n+new file",
        )
        db.add(commit)
        db.flush()
        updated_round = submit_work_item_review(db, "requirement", requirement.id, developer, commit=commit)
        assert updated_round.id == manual_round.id
        assert updated_round.latest_commit_id == commit.id
        assert db.query(WorkItemReviewRound).filter(WorkItemReviewRound.object_id == requirement.id).count() == 1
        db.commit()

        context_with_diff = client.get(
            f"/api/v1/devops/work-item-reviews/requirement/{requirement.id}/context",
            headers={"Authorization": f"Bearer {create_access_token(lead.username)}"},
        )
        assert context_with_diff.status_code == 200, context_with_diff.text
        assert context_with_diff.json()["commit"]["id"] == commit.id
        assert context_with_diff.json()["has_diff"] is True
        assert context_with_diff.json()["diff_text"] == commit.diff_text
    finally:
        db.close()


def test_pending_review_without_round_recovers_context_for_project_development_lead(client):
    db = SessionLocal()
    try:
        reviewer = db.query(User).filter(User.username == "bob", User.deleted == 0, User.is_active.is_(True)).one()
        project = Project(name=f"Legacy review {uuid4().hex[:8]}", **initial_system_workflow_values(db, "project"))
        db.add(project)
        db.flush()
        db.add(ProjectMember(project_id=project.id, user_id=reviewer.id, project_role="development_lead"))
        iteration = create_unstarted_iteration(db, project.id)
        requirement = Requirement(
            project_id=project.id,
            iteration_id=iteration.id,
            title="Legacy pending review requirement",
            owner_id=reviewer.id,
            **initial_workflow_values(db, "requirement", project.id),
        )
        db.add(requirement)
        db.flush()
        approve = db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == requirement.workflow_definition_id,
            WorkflowTransition.action_key == "approve_review",
        ).one()
        requirement.current_state_id = approve.from_state_id
        db.commit()

        context = client.get(
            f"/api/v1/devops/work-item-reviews/requirement/{requirement.id}/context",
            headers={"Authorization": f"Bearer {create_access_token(reviewer.username)}"},
        )

        assert context.status_code == 200, context.text
        assert context.json()["has_diff"] is False
        assert context.json()["review_round"]["reviewer_id"] == reviewer.id
        db.rollback()
        round_row = db.query(WorkItemReviewRound).filter(
            WorkItemReviewRound.object_type == "requirement",
            WorkItemReviewRound.object_id == requirement.id,
            WorkItemReviewRound.status == "open",
        ).one()
        assert round_row.latest_commit_id is None
    finally:
        db.close()


def test_review_api_and_workbench_expose_only_assigned_open_reviews(client):
    db = SessionLocal()
    try:
        lead = _user(db, "development_lead")
        other_lead = _user(db, "development_lead")
        project = Project(name=f"Review API {uuid4().hex[:8]}", **initial_system_workflow_values(db, "project"))
        db.add(project)
        db.flush()
        iteration = create_unstarted_iteration(db, project.id)
        requirement = Requirement(
            project_id=project.id,
            iteration_id=iteration.id,
            title="Review API requirement",
            **initial_workflow_values(db, "requirement", project.id),
        )
        db.add(requirement)
        db.flush()
        submit = db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == requirement.workflow_definition_id,
            WorkflowTransition.action_key == "submit_review",
        ).first()
        requirement.current_state_id = submit.to_state_id
        commit = DevopsCommit(provider="gitea", commit_sha=f"api{uuid4().hex}")
        db.add(commit)
        db.flush()
        review_round = WorkItemReviewRound(
            object_type="requirement",
            object_id=requirement.id,
            latest_commit_id=commit.id,
            reviewer_id=lead.id,
            status="open",
            active_key="open",
        )
        db.add(review_round)
        db.commit()

        lead_headers = {"Authorization": f"Bearer {create_access_token(lead.username)}"}
        other_headers = {"Authorization": f"Bearer {create_access_token(other_lead.username)}"}
        mine = client.get("/api/v1/devops/work-item-reviews", headers=lead_headers)
        other = client.get("/api/v1/devops/work-item-reviews", headers=other_headers)
        workbench = client.get("/api/v1/dashboard/workbench", headers=lead_headers)

        assert [item["id"] for item in mine.json()] == [review_round.id]
        assert other.json() == []
        assert [item["id"] for item in workbench.json()["work_item_reviews"]] == [review_round.id]

        approved = client.post(
            f"/api/v1/devops/work-item-reviews/{review_round.id}/decision",
            json={"decision": "approve"},
            headers=lead_headers,
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"
        assert client.get("/api/v1/devops/work-item-reviews", headers=lead_headers).json() == []
    finally:
        db.close()
