# Workflow Designer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a first-version visual workflow designer where users add trigger, condition, and action components to a workflow canvas, connect parent-child trigger relationships, configure node properties, and persist rules to `workflow_rules`.

**Architecture:** The backend exposes workflow rule CRUD plus component/template metadata. The frontend adds a `/workflow` page with a component palette, drag-enabled canvas nodes, edge creation controls, and a property panel; saving maps canvas data to `condition_json` and executable summary data to `action_json`.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Element Plus, native HTML drag events, existing Axios wrapper.

---

### Task 1: Backend Workflow DTOs, Service, Controller

**Files:**
- Create: `backend/app/views/workflow_view.py`
- Create: `backend/app/services/workflow_service.py`
- Create: `backend/app/controllers/workflow_controller.py`
- Modify: `backend/app/controllers/router.py`
- Test: `backend/tests/test_workflow_rules_api.py`

**Steps:**

1. Create Pydantic DTOs for create, update, read, component, and template responses.
2. Add service functions for list, create, update, delete, components, and templates.
3. Add controller routes under `/workflow-rules`.
4. Include the workflow controller in the API router.
5. Add tests for component metadata, template metadata, and CRUD persistence.

### Task 2: Frontend API And Route

**Files:**
- Create: `frontend/src/api/workflowRules.js`
- Create: `frontend/src/views/WorkflowView.vue`
- Modify: `frontend/src/router/index.js`

**Steps:**

1. Add API helpers for CRUD, components, and templates.
2. Register `/workflow` route.
3. Add a basic page that loads components, templates, and existing rules.
4. Verify the side menu route opens the page.

### Task 3: Workflow Designer UI

**Files:**
- Modify: `frontend/src/views/WorkflowView.vue`

**Steps:**

1. Build the three-column layout: component palette, canvas, property panel.
2. Support drag or click to add a component node.
3. Render nodes with category-specific styling.
4. Allow selecting a node and editing its config.
5. Allow creating parent-child edges using a source node and target node selector.
6. Render simple connector lines/labels as an edge list on the canvas.

### Task 4: Rule Save/Load

**Files:**
- Modify: `frontend/src/views/WorkflowView.vue`

**Steps:**

1. Build `condition_json` from canvas nodes and edges.
2. Build `action_json` summary from trigger and downstream nodes.
3. Save a new rule or update the selected rule.
4. Load an existing rule back into the canvas.
5. Add delete behavior.
6. Add a template loader for the project-close example.

### Task 5: Docs And Verification

**Files:**
- Modify: `docs/prd/2026-06-09-intellective-bio-sdlc-prd.md`
- Modify: `docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md` if API semantics need mention.

**Commands:**

1. `E:\\miniconda3\\envs\\soar_sdlc_py311\\python.exe -m pytest backend/tests/test_workflow_rules_api.py -q`
2. `npm run build`
3. `git diff --check`
4. Commit and push:
   - `git add .`
   - `git commit -m "feat: add workflow designer"`
   - `git -c http.version=HTTP/1.1 push`
