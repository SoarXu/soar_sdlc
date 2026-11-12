import pytest

from app.db.session import SessionLocal
from app.models.devops import WorkItemReviewRound
from app.models.project_member import ProjectMember
from app.models.project import Project
from app.models.status_operation import StatusOperationLog
from app.models.user import User
from app.models.workflow_definition import WorkflowTransition, WorkflowTransitionRole
from app.services.dashboard_service import _work_item_reviews
from test_configured_work_item_review_api import _configured_item, _headers


@pytest.mark.parametrize("object_type", ["requirement", "task", "bug"])
@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_replacement_role_holder_can_handle_old_round(client, object_type, decision):
    data = _configured_item(object_type)
    base = f"/api/v1/devops/work-item-reviews/{object_type}/{data['id']}"
    submitted = client.post(f"{base}/submit", headers=_headers(data["developer"]))
    assert submitted.status_code == 200, submitted.text
    round_id = submitted.json()["id"]
    with SessionLocal() as db:
        db.query(ProjectMember).filter_by(project_id=data["project_id"], user_id=data["reviewer_id"]).delete()
        db.commit()
    assert client.get(f"{base}/context", headers=_headers(data["reviewer"])).status_code == 403
    denied = client.post(f"/api/v1/devops/work-item-reviews/{round_id}/decision",
                         json={"decision": decision, "remark": "former reviewer"},
                         headers=_headers(data["reviewer"]))
    assert denied.status_code == 403
    old_list = client.get("/api/v1/devops/work-item-reviews", headers=_headers(data["reviewer"]))
    assert round_id not in [row["id"] for row in old_list.json()]
    context = client.get(f"{base}/context", headers=_headers(data["outsider"]))
    assert context.status_code == 200, context.text
    listed = client.get("/api/v1/devops/work-item-reviews", headers=_headers(data["outsider"]))
    assert round_id in [row["id"] for row in listed.json()]
    with SessionLocal() as db:
        assert round_id in [row["id"] for row in _work_item_reviews(db, data["outsider_id"])]
    response = client.post(f"/api/v1/devops/work-item-reviews/{round_id}/decision",
                           json={"decision": decision, "remark": "review by replacement"},
                           headers=_headers(data["outsider"]))
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        review = db.get(WorkItemReviewRound, round_id)
        assert review.reviewer_id == data["reviewer_id"]
        assert review.decision_by_id == data["outsider_id"]
    repeated = client.post(f"/api/v1/devops/work-item-reviews/{round_id}/decision",
                          json={"decision": "approve"}, headers=_headers(data["outsider"]))
    assert repeated.status_code == 409


def test_replacement_can_recover_legacy_review_with_departed_owner(client):
    data = _configured_item("task")
    with SessionLocal() as db:
        item = db.get(data["model"], data["id"])
        item.current_state_id = data["review_state_id"]
        item.owner_id = data["reviewer_id"]
        db.get(User, data["reviewer_id"]).is_active = False
        db.query(ProjectMember).filter_by(project_id=data["project_id"], user_id=data["reviewer_id"]).delete()
        db.commit()
    context = client.get(f"/api/v1/devops/work-item-reviews/task/{data['id']}/context",
                         headers=_headers(data["outsider"]))
    assert context.status_code == 200, context.text
    assert context.json()["review_round"]["reviewer_id"] == data["outsider_id"]


@pytest.mark.parametrize("authorization", ["project_member", "current_handler", "approve_only", "reject_only"])
def test_each_review_action_honors_current_workflow_configuration(client, authorization):
    data = _configured_item("requirement")
    base = f"/api/v1/devops/work-item-reviews/requirement/{data['id']}"
    review = client.post(f"{base}/submit", headers=_headers(data["developer"])).json()
    with SessionLocal() as db:
        item = db.get(data["model"], data["id"])
        for transition in db.query(WorkflowTransition).filter_by(
            definition_id=item.workflow_definition_id, from_state_id=item.current_state_id,
        ).all():
            if authorization in {"project_member", "current_handler"}:
                db.query(WorkflowTransitionRole).filter_by(transition_id=transition.id, purpose="allowed").delete()
                transition.allowed_roles = authorization
                transition.ui_config = {"handler_scope": "allowed_identity"}
            elif transition.action_key == ("reject_review" if authorization == "approve_only" else "approve_review"):
                db.query(WorkflowTransitionRole).filter_by(transition_id=transition.id, purpose="allowed").delete()
                transition.allowed_roles = "creator"
        db.commit()
    actor = data["outsider"]
    context = client.get(f"{base}/context", headers=_headers(actor))
    if authorization == "current_handler":
        assert context.status_code == 403
        assert client.get(f"{base}/context", headers=_headers(data["reviewer"])).status_code == 200
        return
    assert context.status_code == 200, context.text
    if authorization in {"approve_only", "reject_only"}:
        denied_decision = "reject" if authorization == "approve_only" else "approve"
        denied = client.post(f"/api/v1/devops/work-item-reviews/{review['id']}/decision",
                             json={"decision": denied_decision, "remark": "reason"}, headers=_headers(actor))
        assert denied.status_code == 403
    decision = "reject" if authorization == "reject_only" else "approve"
    result = client.post(f"/api/v1/devops/work-item-reviews/{review['id']}/decision",
                         json={"decision": decision, "remark": "reason"}, headers=_headers(actor))
    assert result.status_code == 200, result.text


def test_explicit_current_handler_scope_still_restricts_same_role_peer(client):
    data = _configured_item("task")
    base = f"/api/v1/devops/work-item-reviews/task/{data['id']}"
    review = client.post(f"{base}/submit", headers=_headers(data["developer"])).json()
    with SessionLocal() as db:
        item = db.get(data["model"], data["id"])
        for transition in db.query(WorkflowTransition).filter_by(
            definition_id=item.workflow_definition_id, from_state_id=item.current_state_id,
        ).all():
            transition.ui_config = {"handler_scope": "current_handler"}
        db.commit()
    assert client.get(f"{base}/context", headers=_headers(data["outsider"])).status_code == 403
    denied = client.post(f"/api/v1/devops/work-item-reviews/{review['id']}/decision",
                         json={"decision": "approve"}, headers=_headers(data["outsider"]))
    assert denied.status_code == 403
    assert client.get(f"{base}/context", headers=_headers(data["reviewer"])).status_code == 200


@pytest.mark.parametrize("management_identity", ["project_owner", "system_admin"])
def test_authorized_replacement_with_management_identity_is_not_delegating(client, management_identity):
    data = _configured_item("task")
    review = client.post(f"/api/v1/devops/work-item-reviews/task/{data['id']}/submit",
                         headers=_headers(data["developer"])).json()
    with SessionLocal() as db:
        if management_identity == "project_owner":
            db.get(Project, data["project_id"]).owner_id = data["outsider_id"]
        else:
            db.get(User, data["outsider_id"]).is_system_admin = True
        db.commit()
    transitions = client.get(f"/api/v1/workflow-runtime/task/{data['id']}/transitions",
                             headers=_headers(data["outsider"]))
    assert transitions.status_code == 200, transitions.text
    actions = [row for row in transitions.json() if row["action_key"] in {"approve_review", "reject_review"}]
    assert len(actions) == 2
    result = client.post(f"/api/v1/devops/work-item-reviews/{review['id']}/decision",
                         json={"decision": "approve"}, headers=_headers(data["outsider"]))
    assert result.status_code == 200, result.text
    with SessionLocal() as db:
        operation = db.query(StatusOperationLog).filter_by(
            object_type="task", object_id=data["id"], action="approve_review",
        ).one()
        assert operation.is_delegated is False
