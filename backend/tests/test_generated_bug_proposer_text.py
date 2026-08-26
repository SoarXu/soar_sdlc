from types import SimpleNamespace

from app.controllers import test_case_controller, test_run_controller
from app.views.bug_view import BugFromTestRunCaseRequest
from app.views.test_case_view import BugFromTestCaseRequest


def test_generated_bug_requests_accept_free_text_proposer():
    from_case = BugFromTestCaseRequest(title="Case bug", proposer="外部验收人员")
    from_run = BugFromTestRunCaseRequest(title="Run bug", proposer="供应商测试代表")

    assert from_case.proposer == "外部验收人员"
    assert from_run.proposer == "供应商测试代表"


def test_test_case_bug_defaults_proposer_to_current_user_name(monkeypatch):
    payload = BugFromTestCaseRequest(title="Case bug")
    current_user = SimpleNamespace(id=9, full_name="现场测试 张三", username="tester.zhang")
    captured = {}
    monkeypatch.setattr(test_case_controller, "get_test_case", lambda _db, _id: SimpleNamespace(project_id=7))
    monkeypatch.setattr(test_case_controller, "ensure_test_case_execute_permission", lambda *_args: None)
    monkeypatch.setattr(
        test_case_controller,
        "create_bug_from_test_case",
        lambda _db, _id, request, actor_id: captured.update(payload=request, actor_id=actor_id) or request,
    )

    test_case_controller.post_bug_from_test_case(3, payload, db=object(), current_user=current_user)

    assert captured["payload"].proposer == "现场测试 张三"
    assert captured["actor_id"] == 9


def test_test_run_bug_defaults_proposer_to_current_user_name(monkeypatch):
    payload = BugFromTestRunCaseRequest(title="Run bug")
    current_user = SimpleNamespace(id=11, full_name="", username="tester.li")
    captured = {}
    monkeypatch.setattr(test_run_controller, "_get_test_run_for_case", lambda _db, _id: SimpleNamespace(project_id=8))
    monkeypatch.setattr(test_run_controller, "ensure_test_case_execute_permission", lambda *_args: None)
    monkeypatch.setattr(
        test_run_controller,
        "create_bug_from_test_run_case",
        lambda _db, _id, request, actor_id: captured.update(payload=request, actor_id=actor_id) or request,
    )

    test_run_controller.post_bug_from_test_run_case(4, payload, db=object(), current_user=current_user)

    assert captured["payload"].proposer == "tester.li"
    assert captured["actor_id"] == 11
