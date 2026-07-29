# Git Platform Integration Design

## Goal

Add an administrator-managed DevOps Git platform configuration capability. Administrators can configure, test, edit, and remove connections to Gitea, GitLab, and GitHub. Repository synchronization, webhooks, commits, reviews, and work-item associations are out of scope for this phase.

## User Experience

DevOps gains a **Git Platforms** tab ahead of the existing commit, code review, repository, and Jenkins tabs. The list shows display name, provider, server URL, authenticated account, enabled state, latest verification result, verification time, and recent error. Create and edit capture display name, provider, service URL, personal access token, and enabled state. Tokens are accepted only on create or explicit replacement and are never returned to the browser.

## Backend Contract

Add a provider-neutral `git_platform_connections` table containing connection metadata, encrypted token material, authenticated username, connection status, latest verification timestamp, and error text. Add CRUD APIs plus a test endpoint. Provider adapters authenticate against `GET /api/v1/user` for Gitea, `GET /api/v4/user` for GitLab, and `GET /user` for GitHub. Failures remain visible on the saved connection and tokens are omitted from every response.

## Frontend Contract

Add a dedicated API client and Git Platforms tab in `DevopsView`. The page uses existing Element Plus list, dialog, form, confirmation, and feedback conventions. The provider selector supports Gitea, GitLab, and GitHub; the URL field explains the expected endpoint shape.

## Authorization And Verification

Existing system-admin authorization protects create, edit, test, and delete operations. Connection requests use bounded timeouts and safe error messages. Tests cover token redaction, token replacement, provider URL/header handling, API lifecycle, frontend validation, and a manual Gitea test at `http://10.56.0.242:3002`.
