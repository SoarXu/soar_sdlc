import ast
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.api_error_contract import normalize_http_exception_detail


def test_normalizes_registered_legacy_detail_to_chinese_contract():
    detail = normalize_http_exception_detail(
        HTTPException(status_code=404, detail="Iteration not found")
    )

    assert detail == {
        "code": "ITERATION_NOT_FOUND",
        "message": "未找到迭代",
    }


def test_preserves_structured_detail_extensions():
    detail = normalize_http_exception_detail(
        HTTPException(
            status_code=409,
            detail={
                "code": "ITERATION_HAS_OPEN_ITEMS",
                "message": "迭代仍有未完成事项",
                "counts": {"task": 2},
            },
        )
    )

    assert detail == {
        "code": "ITERATION_HAS_OPEN_ITEMS",
        "message": "迭代仍有未完成事项",
        "counts": {"task": 2},
    }


def test_rejects_unregistered_legacy_detail():
    with pytest.raises(AssertionError, match="unregistered legacy error"):
        normalize_http_exception_detail(
            HTTPException(status_code=400, detail="Unexpected legacy error")
        )


def test_http_exception_response_uses_code_and_chinese_message(client):
    response = client.get("/api/v1/iterations/999999999/detail")

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"].startswith("LEGACY_ERROR_")
    assert detail["message"] == "无权限管理迭代交付"


def test_request_validation_response_uses_code_and_chinese_message(client):
    response = client.post("/api/v1/iterations", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "REQUEST_VALIDATION_ERROR"
    assert detail["message"]
    assert all("\u4e00" <= char <= "\u9fff" or not char.isalpha() for char in detail["message"])


def test_all_static_legacy_http_messages_convert_to_chinese_contract():
    errors = []
    for message in _static_legacy_http_messages():
        try:
            detail = normalize_http_exception_detail(HTTPException(status_code=400, detail=message))
        except AssertionError as exc:
            errors.append(str(exc))
            continue
        if any(char.isascii() and char.isalpha() for char in detail["message"]):
            errors.append(f"English message remains: {message!r}")
    assert not errors, "\n".join(errors)


def test_all_formatted_legacy_http_messages_convert_to_chinese_contract():
    errors = []
    for message in _formatted_legacy_http_message_templates():
        try:
            detail = normalize_http_exception_detail(HTTPException(status_code=400, detail=message))
        except AssertionError as exc:
            errors.append(str(exc))
            continue
        if any(char.isascii() and char.isalpha() for char in detail["message"]):
            errors.append(f"English message remains: {message!r}")
    assert not errors, "\n".join(errors)


def _static_legacy_http_messages() -> set[str]:
    messages = set()
    app_root = Path(__file__).resolve().parents[1] / "app"
    for path in app_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "HTTPException":
                continue
            detail = next((keyword.value for keyword in node.keywords if keyword.arg == "detail"), None)
            if isinstance(detail, ast.Constant) and isinstance(detail.value, str) and _has_ascii_letters(detail.value):
                messages.add(detail.value)
            if isinstance(detail, ast.Dict):
                for key, value in zip(detail.keys, detail.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "message"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                        and _has_ascii_letters(value.value)
                    ):
                        messages.add(value.value)
    return messages


def _formatted_legacy_http_message_templates() -> set[str]:
    messages = set()
    app_root = Path(__file__).resolve().parents[1] / "app"
    for path in app_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "HTTPException":
                continue
            detail = next((keyword.value for keyword in node.keywords if keyword.arg == "detail"), None)
            if isinstance(detail, ast.JoinedStr):
                template = "".join(
                    part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "1"
                    for part in detail.values
                )
                if _has_ascii_letters(template):
                    messages.add(template)
    return messages


def _has_ascii_letters(value: str) -> bool:
    return any(char.isascii() and char.isalpha() for char in value)
