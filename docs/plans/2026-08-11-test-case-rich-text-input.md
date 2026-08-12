# 测试用例富文本输入 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the precondition, whole case procedure, and overall expected-result fields support sanitized rich-text entry, without a step-by-step authoring table, and render the stored HTML in the test-case detail view.

**Architecture:** Reuse the application's `RichTextPasteEditor` at both target authoring entry points and persist the whole procedure in a dedicated nullable `steps_content` column. Map `precondition`, `steps_content`, and `expected_result` to MySQL `MEDIUMTEXT` so pasted base64 screenshots can exceed 64 KiB. Untouched legacy records retain `steps_json`; records without `steps_content` derive editable/display HTML by escaping and labeling every legacy step and expected value. Saving either authoring form stores the rich field and explicitly clears `steps_json`, including when the editor is semantically empty, so removed legacy content cannot reappear. Execution entry points create one rich execution row from `steps_content` and the overall expected result, while untouched legacy records retain their structured rows. Sanitize model values before editor DOM assignment and sanitize all rich HTML with DOMPurify before rendering.

**Tech Stack:** Vue 3 Composition API, Element Plus, DOMPurify, SQLAlchemy, Pydantic, Alembic, Node built-in assertions, Pytest, Vite.

---

### Task 1: Add the failing rich-text source contract

**Files:**
- Create: `frontend/src/views/testCaseRichTextInput.test.mjs`
- Test: `frontend/src/views/testCaseRichTextInput.test.mjs`

**Step 1: Write the failing test**

Create backend persistence/schema tests and frontend helper/source tests. Cover the dedicated `steps_content` payload, unchanged legacy `steps_json`, legacy plain-text escaping, semantic-empty editor HTML, image-only content, DOMPurify attack cases, rich/legacy execution fallback, three editor bindings, and removal of the step-row authoring controls.

**Step 2: Run test to verify it fails**

Run: `npm test testCaseRichTextInput`

Expected: FAIL because the backend field, migration, safe conversion helpers, execution adapters, and rich-text authoring contract do not exist.

### Task 2: Use the shared rich-text editor in all test-case forms

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue:593-604`
- Modify: `frontend/src/views/TestCaseDetailView.vue:25-36`
- Modify: `frontend/src/views/TestCaseDetailView.vue:55-67`
- Test: `frontend/src/views/testCaseRichTextInput.test.mjs`

**Step 1: Add the compatibility conversion**

Add `steps_content` to the SQLAlchemy model, Pydantic create/update/read views, dashboard item view, runtime schema bootstrap, and an Alembic migration. Use SQLAlchemy MySQL type variants and dialect-aware migration operations to make all three rich fields `MEDIUMTEXT`; retain portable `Text` on other databases. Do not migrate or overwrite legacy `steps_json`.

**Step 2: Implement the authoring UI change**

Add helpers that escape legacy plain step/expected text, detect semantic editor emptiness, preserve image-only content, sanitize rich HTML with DOMPurify, and build rich or legacy execution rows. Replace the precondition, step-table, and expected-result authoring controls with one editor per field; save `steps_content` and explicitly submit `steps_json: null`. Ensure editor model synchronization sanitizes before comparing with or assigning to `innerHTML`.

**Step 3: Render stored content**

In the test-case detail and execution surfaces, render precondition, the converted whole procedure, overall expected result, and execution step/expected cells with sanitized HTML. Apply the execution adapter in project, dashboard, iteration, Bug, test-management, and requirement-detail entry points.

**Step 4: Run the contract test to verify it passes**

Run: `npm test testCaseRichTextInput`

Expected: PASS and output confirms the rich-text input contract.

### Task 3: Verify the integrated frontend

**Files:**
- Test: `frontend/src/views/testCaseRichTextInput.test.mjs`

**Step 1: Run all frontend source tests**

Run: `npm test`

Expected: PASS with every `.test.mjs` contract completing successfully.

**Step 2: Build the production bundle**

Run: `npm run build`

Expected: Vite production build completes without errors.

**Step 3: Perform a focused manual check**

Create or edit a test case from the project page, paste formatted text and an image into all three narrative fields, save it, and confirm the test-case detail page preserves formatting and images. Repeat from the test-case detail edit form.

**Step 4: Git handling**

Do not stage, commit, push, create a pull request, or merge. Request the required delivery instruction from the user after implementation and verification.
