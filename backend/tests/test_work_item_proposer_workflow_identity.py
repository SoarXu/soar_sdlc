from types import SimpleNamespace

from app.services import workflow_runtime_service
from app.services.default_workflow_template_service import graph_for_object_type
from app.services.workflow_definition_service import HANDLER_SOURCE_TYPES, IDENTITY_ROLES


def test_workflow_registry_excludes_proposer_and_reporter_identities():
    assert {"proposer", "reporter"}.isdisjoint(IDENTITY_ROLES)
    assert {"proposer", "reporter", "bug_reporter"}.isdisjoint(HANDLER_SOURCE_TYPES)


def test_default_bug_workflow_does_not_grant_reporter_permissions():
    graph = graph_for_object_type("bug")

    for transition in graph.transitions:
        identities = {
            value.strip()
            for value in str(transition.allowed_roles or "").split(",")
            if value.strip()
        }
        assert "reporter" not in identities, transition.action_key


def test_bug_verifier_falls_back_to_project_tester_without_reporter_identity(monkeypatch):
    bug = SimpleNamespace(project_id=7, proposer="外部客户")
    monkeypatch.setattr(workflow_runtime_service, "_bug_test_executor_id", lambda _db, _bug: None)
    monkeypatch.setattr(workflow_runtime_service, "_bug_test_case", lambda _db, _bug: None)
    monkeypatch.setattr(workflow_runtime_service, "_project_default_tester_id", lambda _db, _project_id: 42)

    owner_id, source = workflow_runtime_service._bug_verifier_owner(object(), bug, {})

    assert owner_id == 42
    assert source == "bug_verifier:project_tester"


def test_bug_fix_task_confirmation_uses_verifier_without_reporter_identity(monkeypatch):
    task = SimpleNamespace(task_type="bug_fix")
    bug = SimpleNamespace(proposer="外部客户", verified_by=51)
    monkeypatch.setattr(workflow_runtime_service, "_task_source_bug", lambda _db, _task: bug)

    owner_id, source = workflow_runtime_service._task_confirmation_owner(object(), task)

    assert owner_id == 51
    assert source == "task_confirmation:bug_verifier"
