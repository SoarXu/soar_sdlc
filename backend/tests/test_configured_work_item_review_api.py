from datetime import date
from uuid import uuid4

import pytest

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from fastapi import HTTPException

from app.models.devops import DevopsCommit, WorkItemReviewRound
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import Role, RoleCapability
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.models.user import User
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition, WorkflowTransitionRole
from app.services.iteration_assignment_service import create_unstarted_iteration
from app.services.work_item_review_service import submit_work_item_review
from app.services.workflow_state_service import initial_system_workflow_values


def _headers(username):
    return {"Authorization": f"Bearer {create_access_token(username)}"}


def _configured_item(object_type, *, reviewer_active=True, decisions_match=True):
    with SessionLocal() as db:
        suffix = uuid4().hex[:10]
        users = []
        for label in ("developer", "reviewer", "outsider"):
            user = User(username=f"configured_{label}_{suffix}", full_name=label,
                        password_hash=get_password_hash("User123456"), is_active=True)
            db.add(user)
            users.append(user)
        db.flush()
        developer, reviewer, outsider = users
        reviewer.is_active = reviewer_active
        role = Role(role_name=f"code review {suffix}", enabled=True)
        db.add(role)
        project = Project(name=f"Configured review {suffix}", **initial_system_workflow_values(db, "project"))
        db.add(project)
        db.flush()
        developer_role = db.query(Role).join(RoleCapability, RoleCapability.role_id == Role.id).filter(
            RoleCapability.capability == "developer",
        ).one()
        for user, role_id in ((developer, developer_role.id), (reviewer, role.id), (outsider, role.id)):
            db.add(ProjectMember(project_id=project.id, user_id=user.id, role_id=role_id))
        inactive = User(username=f"inactive_reviewer_{suffix}", full_name="Inactive reviewer",
                        password_hash=get_password_hash("User123456"), is_active=False)
        db.add(inactive)
        db.flush()
        db.add(ProjectMember(project_id=project.id, user_id=inactive.id, role_id=role.id, sort_order=-1))
        # Another member with the same workflow role can also handle the review.
        db.flush()
        iteration = create_unstarted_iteration(db, project.id)
        start = db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == iteration.workflow_definition_id,
            WorkflowTransition.action_key == "start",
        ).one()
        iteration.current_state_id = start.to_state_id
        iteration.actual_start_date = date.today()
        definition = WorkflowDefinition(name=f"Configured {object_type} {suffix}", object_type=object_type,
                                        scope_type="project", scope_id=project.id, enabled=True, version=1)
        db.add(definition)
        db.flush()
        states = []
        for name in ("处理中", "Code Review", "评审后"):
            state = WorkflowState(definition_id=definition.id, status_name=name, category="normal", enabled=True)
            db.add(state)
            states.append(state)
        db.flush()
        definition.initial_state_id = states[0].id
        submit = WorkflowTransition(definition_id=definition.id, action_key="submit_review", action_name="提交评审",
                                    from_state_id=states[0].id, to_state_id=states[1].id,
                                    allowed_roles="current_handler", enabled=True,
                                    handler_rule={"target_type": "project_role", "fallback_type": "keep_current"},
                                    ui_config={"handler_scope": "current_handler"})
        db.add(submit)
        db.flush()
        db.add(WorkflowTransitionRole(transition_id=submit.id, purpose="target", role_id=role.id))
        for key in ("approve_review", "reject_review"):
            transition = WorkflowTransition(definition_id=definition.id, action_key=key, action_name=key,
                                            from_state_id=states[1].id, to_state_id=states[2].id,
                                            allowed_roles="", enabled=True, handler_rule={"target_type": "keep_current"},
                                            ui_config={"handler_scope": "allowed_identity"})
            db.add(transition)
            db.flush()
            db.add(WorkflowTransitionRole(transition_id=transition.id, purpose="allowed",
                                         role_id=role.id if decisions_match else developer_role.id))
        model = {"requirement": Requirement, "task": Task, "bug": Bug}[object_type]
        item = model(project_id=project.id, iteration_id=iteration.id, title=f"Review {suffix}",
                     workflow_definition_id=definition.id, current_state_id=states[0].id, owner_id=developer.id)
        db.add(item)
        db.commit()
        return {"id": item.id, "developer": developer.username, "reviewer": reviewer.username,
                "outsider": outsider.username, "reviewer_id": reviewer.id, "project_id": project.id,
                "from_state_id": states[0].id, "review_state_id": states[1].id, "submit_id": submit.id,
                "model": model, "outsider_id": outsider.id}


@pytest.mark.parametrize("object_type", ["requirement", "task", "bug"])
@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_custom_project_role_controls_full_review_flow(client, object_type, decision):
    data = _configured_item(object_type)
    base = f"/api/v1/devops/work-item-reviews/{object_type}/{data['id']}"
    submitted = client.post(f"{base}/submit", headers=_headers(data["developer"]))
    assert submitted.status_code == 200, submitted.text
    review = submitted.json()
    assert review["reviewer_id"] == data["reviewer_id"]
    with SessionLocal() as db:
        item = db.get(data["model"], data["id"])
        assert item.owner_id == review["reviewer_id"]
        assert item.current_state_id == data["review_state_id"]
    context = client.get(f"{base}/context", headers=_headers(data["reviewer"]))
    assert context.status_code == 200, context.text
    peer = client.get(f"{base}/context", headers=_headers(data["outsider"]))
    assert peer.status_code == 200, peer.text
    denied = client.get(f"{base}/context", headers=_headers(data["developer"]))
    assert denied.status_code == 403
    url = f"/api/v1/devops/work-item-reviews/{review['id']}/decision"
    denied = client.post(url, json={"decision": decision, "remark": "reason"}, headers=_headers(data["developer"]))
    assert denied.status_code == 403
    decided = client.post(url, json={"decision": decision, "remark": "reason"}, headers=_headers(data["reviewer"]))
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == ("approved" if decision == "approve" else "rejected")


@pytest.mark.parametrize("problem", ["no_member", "inactive", "permission_mismatch"])
def test_invalid_review_configuration_does_not_change_work_item(client, problem):
    data = _configured_item("requirement", reviewer_active=problem != "inactive",
                            decisions_match=problem != "permission_mismatch")
    with SessionLocal() as db:
        db.query(ProjectMember).filter(ProjectMember.project_id == data["project_id"],
                                       ProjectMember.user_id == data["outsider_id"]).delete()
        if problem == "no_member":
            db.query(ProjectMember).filter(ProjectMember.project_id == data["project_id"],
                                           ProjectMember.user_id == data["reviewer_id"]).delete()
        db.commit()
    response = client.post(f"/api/v1/devops/work-item-reviews/requirement/{data['id']}/submit",
                           headers=_headers(data["developer"]))
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "评审" in (detail.get("message", "") if isinstance(detail, dict) else detail)
    with SessionLocal() as db:
        item = db.get(Requirement, data["id"])
        assert item.current_state_id == data["from_state_id"]
        assert db.query(WorkItemReviewRound).filter_by(object_type="requirement", object_id=item.id).count() == 0
        assert db.query(StatusOperationLog).filter_by(object_type="requirement", object_id=item.id).count() == 0


def test_custom_reviewer_can_recover_legacy_round_but_unauthorized_member_cannot(client):
    data = _configured_item("requirement")
    with SessionLocal() as db:
        item = db.get(Requirement, data["id"])
        item.current_state_id = data["review_state_id"]
        item.owner_id = data["reviewer_id"]
        db.commit()
    url = f"/api/v1/devops/work-item-reviews/requirement/{data['id']}/context"
    denied = client.get(url, headers=_headers(data["developer"]))
    assert denied.status_code == 403
    context = client.get(url, headers=_headers(data["reviewer"]))
    assert context.status_code == 200, context.text
    assert context.json()["review_round"]["reviewer_id"] == data["reviewer_id"]


def test_fixed_user_review_assignment_is_respected(client):
    data = _configured_item("task")
    with SessionLocal() as db:
        transition = db.get(WorkflowTransition, data["submit_id"])
        transition.handler_rule = {"target_type": "fixed_user", "fixed_user_id": data["reviewer_id"]}
        db.commit()
    submitted = client.post(f"/api/v1/devops/work-item-reviews/task/{data['id']}/submit",
                            headers=_headers(data["developer"]))
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["reviewer_id"] == data["reviewer_id"]


def test_caught_submission_failure_can_commit_other_work_without_partial_transition(client):
    data = _configured_item("requirement", decisions_match=False)
    with SessionLocal() as db:
        actor = db.query(User).filter_by(username=data["developer"]).one()
        with pytest.raises(HTTPException):
            submit_work_item_review(db, "requirement", data["id"], actor)
        db.commit()
        assert db.get(Requirement, data["id"]).current_state_id == data["from_state_id"]
        assert db.query(WorkItemReviewRound).filter_by(object_type="requirement", object_id=data["id"]).count() == 0
        assert db.query(StatusOperationLog).filter_by(object_type="requirement", object_id=data["id"]).count() == 0


def test_git_submission_reuses_the_configured_reviewer_and_active_round(client):
    data = _configured_item("requirement")
    with SessionLocal() as db:
        actor = db.query(User).filter_by(username=data["developer"]).one()
        first = submit_work_item_review(db, "requirement", data["id"], actor)
        commit = DevopsCommit(provider="gitea", commit_sha=uuid4().hex)
        db.add(commit)
        db.flush()
        second = submit_work_item_review(db, "requirement", data["id"], actor, commit=commit)
        assert second.id == first.id
        assert second.reviewer_id == data["reviewer_id"]
        assert second.latest_commit_id == commit.id
        assert db.query(WorkItemReviewRound).filter_by(object_type="requirement", object_id=data["id"]).count() == 1


@pytest.mark.parametrize("object_type", ["requirement", "task", "bug"])
def test_legacy_default_submission_routes_to_configured_default_review_role(client, object_type):
    data = _configured_item(object_type)
    with SessionLocal() as db:
        lead_role_id = db.query(RoleCapability.role_id).filter_by(capability="development_lead").scalar()
        transition = db.get(WorkflowTransition, data["submit_id"])
        transition.handler_rule = {"target_type": "keep_current", "fallback_type": "keep_current"}
        db.query(WorkflowTransitionRole).filter_by(transition_id=transition.id, purpose="target").delete()
        decisions = db.query(WorkflowTransition.id).filter(
            WorkflowTransition.definition_id == transition.definition_id,
            WorkflowTransition.action_key.in_({"approve_review", "reject_review"}),
        )
        db.query(WorkflowTransitionRole).filter(
            WorkflowTransitionRole.transition_id.in_(decisions), WorkflowTransitionRole.purpose == "allowed",
        ).update({WorkflowTransitionRole.role_id: lead_role_id}, synchronize_session=False)
        db.add(ProjectMember(project_id=data["project_id"], user_id=data["reviewer_id"], role_id=lead_role_id))
        db.commit()
    submitted = client.post(f"/api/v1/devops/work-item-reviews/{object_type}/{data['id']}/submit",
                            headers=_headers(data["developer"]))
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["reviewer_id"] == data["reviewer_id"]
    with SessionLocal() as db:
        assert db.get(WorkflowTransition, data["submit_id"]).handler_rule["target_type"] == "project_role"


def test_existing_round_preserves_designated_reviewer_when_legacy_owner_differs(client):
    data = _configured_item("requirement")
    with SessionLocal() as db:
        item = db.get(Requirement, data["id"])
        item.current_state_id = data["review_state_id"]
        review = WorkItemReviewRound(object_type="requirement", object_id=item.id,
                                    reviewer_id=data["reviewer_id"], status="open", active_key="open")
        db.add(review)
        db.commit()
        round_id = review.id
    context = client.get(f"/api/v1/devops/work-item-reviews/requirement/{data['id']}/context",
                         headers=_headers(data["reviewer"]))
    assert context.status_code == 200, context.text
    decided = client.post(f"/api/v1/devops/work-item-reviews/{round_id}/decision",
                          json={"decision": "approve"}, headers=_headers(data["reviewer"]))
    assert decided.status_code == 200, decided.text


def test_explicit_custom_keep_current_assignment_is_not_overwritten(client):
    data = _configured_item("task")
    with SessionLocal() as db:
        transition = db.get(WorkflowTransition, data["submit_id"])
        role_id = db.query(WorkflowTransitionRole.role_id).filter_by(transition_id=transition.id, purpose="target").scalar()
        developer = db.query(User).filter_by(username=data["developer"]).one()
        developer_id = developer.id
        db.add(ProjectMember(project_id=data["project_id"], user_id=developer.id, role_id=role_id))
        transition.handler_rule = {"target_type": "keep_current"}
        db.query(WorkflowTransitionRole).filter_by(transition_id=transition.id, purpose="target").delete()
        db.commit()
    submitted = client.post(f"/api/v1/devops/work-item-reviews/task/{data['id']}/submit",
                            headers=_headers(data["developer"]))
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["reviewer_id"] == developer_id
    with SessionLocal() as db:
        assert db.get(WorkflowTransition, data["submit_id"]).handler_rule["target_type"] == "keep_current"
