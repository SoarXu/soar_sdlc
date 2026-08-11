# 测试用例富文本输入 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every test-case narrative field support sanitized rich-text entry and render the stored HTML in the test-case detail view.

**Architecture:** Reuse the application's `RichTextPasteEditor` at both test-case authoring entry points. Keep the existing API and persistence shape unchanged because all target values are already strings; render the editor-sanitized HTML with Vue `v-html` in the detail view.

**Tech Stack:** Vue 3 Composition API, Element Plus, Node built-in assertions, Vite.

---

### Task 1: Add the failing rich-text source contract

**Files:**
- Create: `frontend/src/views/testCaseRichTextInput.test.mjs`
- Test: `frontend/src/views/testCaseRichTextInput.test.mjs`

**Step 1: Write the failing test**

Create a Node assertion test that reads `ProjectDetailView.vue` and `TestCaseDetailView.vue` as UTF-8. Assert that each imports `RichTextPasteEditor`, binds it to `caseForm.precondition` and `caseForm.expected_result`, and binds it in the steps table to `row.step` and `row.expected`. Also assert that the test-case detail display uses `v-html` for the four saved rich-text values.

**Step 2: Run test to verify it fails**

Run: `npm test testCaseRichTextInput`

Expected: FAIL because the test-case source files still use `el-input` and interpolated text for these fields.

### Task 2: Use the shared rich-text editor in all test-case forms

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue:593-604`
- Modify: `frontend/src/views/TestCaseDetailView.vue:25-36`
- Modify: `frontend/src/views/TestCaseDetailView.vue:55-67`
- Test: `frontend/src/views/testCaseRichTextInput.test.mjs`

**Step 1: Implement the minimum UI change**

Import `RichTextPasteEditor` into `TestCaseDetailView.vue`; `ProjectDetailView.vue` already imports it. Replace the two textarea inputs and both inputs in each test-step row at both authoring entry points with `RichTextPasteEditor`, preserving their existing `v-model` expressions, row add/remove behavior and save payloads.

**Step 2: Render stored content**

In `TestCaseDetailView.vue`, replace text interpolation for `precondition`, `expected_result`, `row.step`, and `row.expected` with `v-html`, retaining each existing empty fallback or step-number fallback.

**Step 3: Run the contract test to verify it passes**

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

Create or edit a test case from the project page, paste formatted text and an image into all four narrative field types, save it, and confirm the test-case detail page preserves formatting and images. Repeat from the test-case detail edit form.

**Step 4: Git handling**

Do not stage, commit, push, create a pull request, or merge. Request the required delivery instruction from the user after implementation and verification.
