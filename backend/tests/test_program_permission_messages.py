from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import program_service


def test_program_governance_denials_return_chinese_permission_message(monkeypatch):
    monkeypatch.setattr(program_service, "_get_active_program", lambda *_args: SimpleNamespace())
    monkeypatch.setattr(program_service, "can_delete_program", lambda *_args: False)
    monkeypatch.setattr(program_service, "can_manage_program", lambda *_args: False)
    monkeypatch.setattr(program_service, "can_create_child_program", lambda *_args: False)

    denials = (
        lambda: program_service.delete_program(SimpleNamespace(), 1, 1),
        lambda: program_service._require_program_governance(SimpleNamespace(), 1, 1),
        lambda: program_service._require_child_program_governance(SimpleNamespace(), 1, 1),
    )

    for deny in denials:
        with pytest.raises(HTTPException) as raised:
            deny()

        assert raised.value.status_code == 403
        assert raised.value.detail == "无权限"
