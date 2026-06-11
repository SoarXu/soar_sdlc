# Requirement Create Test Case Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "建用例" action to requirement lists so users can create a test case pre-linked to the selected requirement.

**Architecture:** Reuse the existing test case backend API and project detail test case dialog, adding one persistent `test_scope` field and structured `steps_json` entry. The frontend opens the test case dialog from a requirement row, auto-fills the current project and requirement, and stores ordinary step rows without hierarchy.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL schema migration helper, Vue 3, Element Plus, Vitest/build tooling.

---

### Task 1: Backend Test Case Scope And Steps

**Files:**
- Modify: `backend/app/models/test_case.py`
- Modify: `backend/app/views/test_case_view.py`
- Modify: `backend/app/services/test_case_service.py`
- Modify: `backend/app/db/schema.py`
- Test: `backend/tests/test_testing_bug_api.py`

**Steps:**
1. Add a failing API test that creates a test case with `test_scope` and `steps_json` rows.
2. Run the focused backend test and confirm it fails before implementation.
3. Add `test_scope` to model, create/update request views, service payload handling, and schema ensure helper.
4. Run the focused backend test and confirm it passes.

### Task 2: Frontend Requirement Action And Dialog

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/TestsView.vue`

**Steps:**
1. Add fixed option lists for case type and test scope.
2. Replace free-text case type with select controls.
3. Add `test_scope` and `steps_json` to case form state.
4. Add ordinary steps table with add/delete row actions.
5. Add "建用例" on project detail requirement rows. It opens the case dialog with the selected requirement prefilled.
6. Keep closed-project behavior: the button is disabled when the project is closed.

### Task 3: Documentation

**Files:**
- Modify: `docs/prd/2026-06-09-intellective-bio-sdlc-prd.md`
- Modify: `docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md`
- Modify: `docs/database/init_mysql.sql`

**Steps:**
1. Document the requirement-list "建用例" action.
2. Document fixed test case type and scope options.
3. Document `test_cases.test_scope`.

### Task 4: Verification And Commit

**Commands:**
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_testing_bug_api.py -q`
- `npm run build` from `frontend`
- `git diff --check`
- `git status --short`

**Steps:**
1. Run backend tests.
2. Run frontend build.
3. Check whitespace and git status.
4. Commit and push with message `feat: create test cases from requirements`.
