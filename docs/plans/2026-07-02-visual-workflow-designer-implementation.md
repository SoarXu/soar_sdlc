# Visual Workflow Designer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a visual workflow designer for requirement/task/bug workflows with editable states, transitions, canvas layout, templates, and handler-rule synchronization.

**Architecture:** Add workflow definition, state, and transition tables. Expose graph APIs for CRUD and template application. Implement the frontend designer with Vue and SVG, while reusing existing handler transition rule APIs for runtime handler assignment.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Element Plus, Vite, SVG.

---

### Task 1: Workflow Definition Backend

**Files:**
- Create: `backend/app/models/workflow_definition.py`
- Create: `backend/app/views/workflow_definition_view.py`
- Create: `backend/app/services/workflow_definition_service.py`
- Create: `backend/app/controllers/workflow_definition_controller.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/db/schema.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Steps:**
1. Write failing tests for creating/listing workflow definitions.
2. Run focused test and confirm 404/import failure.
3. Implement model, view, service, controller, and schema creation.
4. Re-run focused tests.

### Task 2: Graph Save And Validation

**Files:**
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/app/views/workflow_definition_view.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Steps:**
1. Write failing tests for saving nodes/transitions and preserving coordinates.
2. Add validation for unique status keys and unique transitions.
3. Add delete protection for referenced states.
4. Re-run focused tests.

### Task 3: Standard Templates

**Files:**
- Modify: `backend/app/services/workflow_definition_service.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Steps:**
1. Write failing tests for applying requirement/task/bug templates.
2. Implement template definitions.
3. Re-run focused tests.

### Task 4: Handler Rule Synchronization

**Files:**
- Modify: `backend/app/services/workflow_definition_service.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Steps:**
1. Write failing test proving transition handler config creates/updates `handler_transition_rules`.
2. Implement synchronization by transition action/from/to status.
3. Re-run focused tests and existing handler transition tests.

### Task 5: Frontend API And Designer

**Files:**
- Create: `frontend/src/api/workflowDefinitions.js`
- Create: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/views/WorkflowView.vue`

**Steps:**
1. Add API client.
2. Build SVG workflow designer component with node drag, edge click, and side panel events.
3. Replace workflow detail default content with visual designer.
4. Keep matrix and advanced rules as compatibility sections.
5. Run frontend build.

### Task 6: Verification And Run

**Commands:**
- `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_workflow_definition_api.py -q`
- `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_handler_transition_matrix_api.py backend\tests\test_handler_transition_rule_api.py -q`
- `npm run build`

**Run services:**
- Backend from `backend`: `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Frontend from `frontend`: `npm run dev -- --host 0.0.0.0`
