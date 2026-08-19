from app.models.project_member import ProjectMember
from app.models.role import Role, RoleCapability
from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.business_component import BusinessComponentMember, BusinessComponentTransitionRoute
from app.models.user import User


def test_system_administrator_is_a_user_attribute():
    assert "is_system_admin" in User.__table__.c


def test_project_member_references_role_by_id():
    assert "role_id" in ProjectMember.__table__.c
    assert "project_role" not in ProjectMember.__table__.c


def test_business_role_has_no_mutable_identifier():
    assert "role_key" not in Role.__table__.c


def test_internal_role_capabilities_reference_business_role_ids():
    assert "role_id" in RoleCapability.__table__.c
    assert "capability" in RoleCapability.__table__.c


def test_assignee_rules_store_business_role_ids():
    assert "requirement_owner_role_ids" in AssigneeRuleConfig.__table__.c
    assert "task_owner_role_ids" in AssigneeRuleConfig.__table__.c
    assert "test_case_tester_role_ids" in AssigneeRuleConfig.__table__.c
    assert "test_run_owner_role_ids" in AssigneeRuleConfig.__table__.c
    assert "bug_owner_role_ids" in AssigneeRuleConfig.__table__.c


def test_business_component_roles_reference_role_ids():
    assert "role_id" in BusinessComponentMember.__table__.c
    assert "eligible_role_ids" in BusinessComponentTransitionRoute.__table__.c
    assert "next_owner_role_ids" in BusinessComponentTransitionRoute.__table__.c
