"""Acceptance tests for project-name uniqueness within a program sibling scope."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _create_program(client: TestClient, name: str | None = None) -> dict:
    response = client.post("/api/v1/programs", json={"name": name or _unique_name("project-name-program")})
    assert response.status_code == 200, response.text
    return response.json()


def _create_project(
    client: TestClient,
    name: str,
    *,
    program_id: int | None = None,
    parent_id: int | None = None,
) -> dict:
    payload = {"name": name}
    if program_id is not None:
        payload["program_id"] = program_id
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _assert_project_name_conflict(response) -> None:
    assert response.status_code == 422
    assert response.json()["detail"] == "项目名称已存在"


def test_rejects_duplicate_sibling_project_name_in_same_program(client: TestClient):
    program = _create_program(client)
    name = _unique_name("same-program-sibling")
    _create_project(client, name, program_id=program["id"])

    duplicate = client.post("/api/v1/projects", json={"name": name, "program_id": program["id"]})

    _assert_project_name_conflict(duplicate)


def test_rejects_case_and_whitespace_variant_of_sibling_project_name(client: TestClient):
    program = _create_program(client)
    name = _unique_name("normalized-project-name")
    _create_project(client, name, program_id=program["id"])

    duplicate = client.post(
        "/api/v1/projects",
        json={"name": f"  {name.upper()}  ", "program_id": program["id"]},
    )

    _assert_project_name_conflict(duplicate)


def test_rejects_project_rename_that_conflicts_with_sibling(client: TestClient):
    program = _create_program(client)
    existing = _create_project(client, _unique_name("rename-existing"), program_id=program["id"])
    renamed = _create_project(client, _unique_name("rename-target"), program_id=program["id"])

    conflict = client.patch(f"/api/v1/projects/{renamed['id']}", json={"name": existing["name"]})

    _assert_project_name_conflict(conflict)


def test_rejects_move_to_parent_or_program_with_same_name_sibling(client: TestClient):
    source_program = _create_program(client)
    target_program = _create_program(client)
    source_parent = _create_project(client, _unique_name("source-parent"), program_id=source_program["id"])
    target_parent = _create_project(client, _unique_name("target-parent"), program_id=target_program["id"])
    name = _unique_name("move-conflict")
    moving = _create_project(client, name, program_id=source_program["id"], parent_id=source_parent["id"])
    _create_project(client, name, program_id=target_program["id"], parent_id=target_parent["id"])

    conflict = client.patch(
        f"/api/v1/projects/{moving['id']}",
        json={"program_id": target_program["id"], "parent_id": target_parent["id"]},
    )

    _assert_project_name_conflict(conflict)


def test_allows_same_project_name_in_different_parent_program_or_unbound_scope(client: TestClient):
    first_program = _create_program(client)
    second_program = _create_program(client)
    first_parent = _create_project(client, _unique_name("first-parent"), program_id=first_program["id"])
    second_parent = _create_project(client, _unique_name("second-parent"), program_id=first_program["id"])
    name = _unique_name("allowed-shared-name")

    _create_project(client, name, program_id=first_program["id"], parent_id=first_parent["id"])
    same_parent_name_in_other_program = client.post(
        "/api/v1/projects",
        json={"name": name, "program_id": second_program["id"], "parent_id": None},
    )
    different_parent = client.post(
        "/api/v1/projects",
        json={"name": name, "program_id": first_program["id"], "parent_id": second_parent["id"]},
    )
    unbound_first = client.post("/api/v1/projects", json={"name": name})
    unbound_second = client.post("/api/v1/projects", json={"name": name})

    assert same_parent_name_in_other_program.status_code == 200, same_parent_name_in_other_program.text
    assert different_parent.status_code == 200, different_parent.text
    assert unbound_first.status_code == 200, unbound_first.text
    assert unbound_second.status_code == 200, unbound_second.text
