import json

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.services import git_platform_service


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


@pytest.fixture(autouse=True)
def git_platform_encryption_key():
    key_name = "git_platform_encryption_key"
    had_value = key_name in settings.__dict__
    previous = settings.__dict__.get(key_name)
    settings.__dict__[key_name] = Fernet.generate_key().decode("utf-8")
    yield
    if had_value:
        settings.__dict__[key_name] = previous
    else:
        settings.__dict__.pop(key_name, None)


def test_git_platform_connection_does_not_return_access_token(client):
    response = client.post(
        "/api/v1/devops/git-platforms",
        json={
            "name": "Local Gitea",
            "provider": "gitea",
            "base_url": "http://10.56.0.242:3002",
            "access_token": "gitea-secret-token",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Local Gitea"
    assert payload["provider"] == "gitea"
    assert payload["has_access_token"] is True
    assert "access_token" not in payload
    assert "gitea-secret-token" not in response.text

    listed = client.get("/api/v1/devops/git-platforms")
    assert listed.status_code == 200
    assert listed.json()[0]["has_access_token"] is True
    assert "access_token" not in listed.json()[0]


@pytest.mark.parametrize(
    ("provider", "base_url", "expected_url", "expected_header", "profile", "expected_username"),
    [
        ("gitea", "http://git.local", "http://git.local/api/v1/user", ("Authorization", "token gitea-token"), {"login": "gitea-user"}, "gitea-user"),
        ("gitlab", "http://git.local", "http://git.local/api/v4/user", ("Private-token", "gitlab-token"), {"username": "gitlab-user"}, "gitlab-user"),
        ("github", "https://api.github.com", "https://api.github.com/user", ("Authorization", "Bearer github-token"), {"login": "github-user"}, "github-user"),
    ],
)
def test_git_platform_connection_test_uses_provider_profile_endpoint(
    client, monkeypatch, provider, base_url, expected_url, expected_header, profile, expected_username
):
    def fake_urlopen(request, timeout):
        assert request.full_url == expected_url
        assert request.get_header(expected_header[0]) == expected_header[1]
        assert timeout == 10
        return FakeResponse(profile)

    monkeypatch.setattr(git_platform_service, "urlopen", fake_urlopen, raising=False)
    created = client.post(
        "/api/v1/devops/git-platforms",
        json={
            "name": f"{provider} connection",
            "provider": provider,
            "base_url": base_url,
            "access_token": f"{provider}-token",
        },
    )

    tested = client.post(f"/api/v1/devops/git-platforms/{created.json()['id']}/test")

    assert tested.status_code == 200
    assert tested.json()["connection_status"] == "connected"
    assert tested.json()["authenticated_username"] == expected_username
    assert tested.json()["last_error"] is None


def test_git_platform_connection_update_preserves_token_and_soft_deletes(client):
    created = client.post(
        "/api/v1/devops/git-platforms",
        json={
            "name": "Update Gitea",
            "provider": "gitea",
            "base_url": "http://git.local",
            "access_token": "keep-this-token",
        },
    ).json()

    updated = client.put(
        f"/api/v1/devops/git-platforms/{created['id']}",
        json={"name": "Renamed Gitea", "enabled": 0},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed Gitea"
    assert updated.json()["enabled"] == 0
    assert updated.json()["has_access_token"] is True

    deleted = client.delete(f"/api/v1/devops/git-platforms/{created['id']}")

    assert deleted.status_code == 204
    assert client.get("/api/v1/devops/git-platforms").json() == []


def test_git_platform_connection_update_invalidates_existing_verification(client, monkeypatch):
    monkeypatch.setattr(git_platform_service, "urlopen", lambda *_args, **_kwargs: FakeResponse({"login": "gitea-user"}), raising=False)
    created = client.post(
        "/api/v1/devops/git-platforms",
        json={"name": "Gitea reset", "provider": "gitea", "base_url": "http://git.local", "access_token": "token"},
    ).json()
    assert client.post(f"/api/v1/devops/git-platforms/{created['id']}/test").json()["connection_status"] == "connected"

    updated = client.put(f"/api/v1/devops/git-platforms/{created['id']}", json={"base_url": "http://git-next.local"})

    assert updated.status_code == 200
    assert updated.json()["connection_status"] == "pending"
    assert updated.json()["authenticated_username"] is None
    assert updated.json()["last_verified_at"] is None


def test_git_platform_list_requires_authentication(client):
    response = client.get("/api/v1/devops/git-platforms", headers={"X-Test-No-Auth": "1"})

    assert response.status_code == 401


def test_git_platform_connection_rejects_non_http_service_url(client):
    response = client.post(
        "/api/v1/devops/git-platforms",
        json={"name": "Invalid URL", "provider": "gitea", "base_url": "file:///etc/passwd", "access_token": "token"},
    )

    assert response.status_code == 422
