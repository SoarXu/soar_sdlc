from app.models.project_member import ProjectMember
from app.models.role import Role
from app.models.user import User


def test_system_administrator_is_a_user_attribute():
    assert "is_system_admin" in User.__table__.c


def test_project_member_references_role_by_id():
    assert "role_id" in ProjectMember.__table__.c
    assert "project_role" not in ProjectMember.__table__.c


def test_business_role_has_no_mutable_identifier():
    assert "role_key" not in Role.__table__.c
