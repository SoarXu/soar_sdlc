# Git Platform Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an administrator-managed Git platform connection page that securely stores and tests Gitea, GitLab, and GitHub credentials.

**Architecture:** A provider-neutral SQLAlchemy model stores connection metadata and encrypted tokens. Provider adapters map each platform to an authenticated-user endpoint and request headers. The DevOps service exposes CRUD and bounded connection tests, and the existing DevOps view receives a Git Platforms tab without changing repository, commit, review, or Jenkins behavior.

**Tech Stack:** Vue 3, Element Plus, Axios, FastAPI, Pydantic v2, SQLAlchemy, `cryptography.fernet`, pytest.

---

### Task 1: Secure connection data

**Files:** `backend/app/models/devops.py`, `backend/app/core/security.py`, `backend/app/views/devops_view.py`, `backend/tests/test_git_platform_connections_api.py`

1. Write a failing API test proving create/list responses never expose `access_token`.
2. Add `DevopsGitPlatformConnection`, create/update/read DTOs, and stable Fernet encryption helpers derived from `settings.secret_key`.
3. Run the focused test until it passes.

### Task 2: Provider adapters and service

**Files:** `backend/app/services/git_platform_service.py`, `backend/app/services/devops_service.py`, `backend/tests/test_git_platform_connections_api.py`

1. Write failing mocked-request tests for Gitea `/api/v1/user`, GitLab `/api/v4/user`, and GitHub `/user` endpoints and their authentication headers.
2. Implement URL normalization, timeout-bounded current-user calls, safe error mapping, create/update/delete helpers, and persisted test outcomes.
3. Verify focused adapter and persistence tests pass.

### Task 3: Protected API endpoints

**Files:** `backend/app/controllers/devops_controller.py`, `backend/app/views/devops_view.py`, `backend/tests/test_git_platform_connections_api.py`

1. Write failing lifecycle and authorization tests for list/create/update/delete/test.
2. Add `GET`, `POST`, `PUT /{id}`, `DELETE /{id}`, and `POST /{id}/test` under `/devops/git-platforms`.
3. Verify new and existing DevOps backend tests pass.

### Task 4: Git Platforms page

**Files:** `frontend/src/api/devops.js`, `frontend/src/views/DevopsView.vue`, `frontend/src/views/devopsGitPlatforms.test.mjs`

1. Write failing frontend tests for required fields, no token prefill during edit, and test-result refresh.
2. Add the API client, first DevOps tab, connection table, create/edit dialog, test/edit/delete actions, validation, status display, and provider-specific placeholders.
3. Verify focused frontend tests pass.

### Task 5: Full verification

Run backend tests, frontend tests, and `npm run build`; then configure and test the local Gitea instance manually. Commit only the Git platform implementation files and these plans.
