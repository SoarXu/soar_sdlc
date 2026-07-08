# 工作流方案项目绑定 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将用户侧概念从“工作流规则/责任人规则”统一为“工作流方案”，并允许项目创建/编辑时直接选择工作流方案。

**Architecture:** 后端技术字段暂时保留 `assignee_rule_config_id`，前端把它作为“工作流方案”展示和维护。工作流配置页维护方案内容和批量项目关联；项目页负责单个项目的方案选择。

**Tech Stack:** Vue 3、Element Plus、Vite、FastAPI 现有项目接口。

---

### Task 1: Add Label Regression Test

**Files:**
- Create: `frontend/src/utils/workflowSchemeLabels.test.mjs`

**Step 1: Write failing test**

Add a Node-based text regression test that checks:
- `ProjectsView.vue` has a “工作流方案” selector bound to `form.assignee_rule_config_id`.
- `WorkflowView.vue` uses “工作流方案” instead of user-facing “工作流规则”.
- `ProjectDetailView.vue` labels `assignee_rule_config_id` as “工作流方案”.

**Step 2: Run test to verify it fails**

Run: `node frontend/src/utils/workflowSchemeLabels.test.mjs`
Expected: FAIL before UI labels are updated.

### Task 2: Update Project Form

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue`

**Steps:**
- Fetch workflow schemes using the existing `fetchAssigneeRuleConfigs` API.
- Add `assignee_rule_config_id` to the project form state.
- Add a “工作流方案” select in create/edit dialog.
- Show the selected scheme in the project list.
- Submit `assignee_rule_config_id` through the existing project create/update payload.

### Task 3: Rename Workflow Config UI

**Files:**
- Modify: `frontend/src/views/WorkflowView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`

**Steps:**
- Rename list/detail labels to “工作流方案”.
- Rename project transfer labels to “切换工作流方案”.
- Keep `assignee_rule_config_id` as the technical field.

### Task 4: Verify

**Commands:**
- `node frontend/src/utils/workflowSchemeLabels.test.mjs`
- `npm run build`

Expected: both commands exit 0.
