# Workflow Advanced Configuration Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the workflow designer's narrow advanced-configuration accordion with a desktop-responsive 520-640px overlay drawer that provides isolated drafts, five focused configuration sections, explicit validation, and two-level saving.

**Architecture:** Keep `WorkflowDesigner.vue` responsible for graph selection and final graph persistence. Move advanced editing into a dedicated `WorkflowAdvancedConfigDrawer.vue`, backed by pure draft/validation helpers in `workflowAdvancedConfig.js`; continue using `workflowTransitionConfig.js` as the backend serializer boundary. No backend API, runtime semantic, database, or migration changes are allowed.

**Tech Stack:** Vue 3 Composition API, Element Plus, existing Node `.test.mjs` runner, Vite.

**Execution constraints:** Work in the current workspace, preserve unrelated changes, do not create a worktree, and do not commit unless explicitly requested. Verify three independent fixed desktop sizes (`1366x768`, `1440x900`, `1920x1080`); do not resize during a run and do not add mobile acceptance tests.

---

## File Structure

- Create `frontend/src/utils/workflowAdvancedConfig.js`: pure cloning, dirty-state, section-state, clearing, validation, and apply helpers.
- Create `frontend/src/utils/workflowAdvancedConfig.test.mjs`: behavior tests for the pure helper boundary.
- Create `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`: drawer shell, five section editors, local draft, close confirmation, and apply event.
- Create `frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`: source-contract checks for the drawer's stable labels and interaction hooks.
- Modify `frontend/src/components/WorkflowDesigner.vue`: remove the old advanced accordion, render summaries and the drawer entry, apply drawer output to the selected transition, and guard navigation.
- Modify `frontend/src/utils/workflowTransitionConfig.js`: only where required to preserve dictionary routing and normalized draft shapes.
- Modify `frontend/src/utils/workflowTransitionConfig.test.mjs`: protect serializer round trips after the UI split.
- Modify `frontend/scripts/verify-fixed-desktop.mjs`: include the workflow route in the fixed desktop smoke pass.

### Task 1: Advanced Configuration Draft Model

**Files:**
- Create: `frontend/src/utils/workflowAdvancedConfig.js`
- Create: `frontend/src/utils/workflowAdvancedConfig.test.mjs`
- Modify: `frontend/src/utils/workflowTransitionConfig.test.mjs`

- [ ] **Step 1: Write failing draft-isolation and apply tests**

Create test fixtures with all advanced sections populated and assert that draft mutation does not mutate the source transition:

```js
const source = normalizeWorkflowTransition({
  action_key: 'verify_failed',
  action_name: '验证未通过',
  from_status: 'pending_verification',
  to_status: 'in_processing',
  allowed_roles: 'tester,project_owner',
  handler_rule: {
    target_type: 'previous_handler',
    target_roles: '',
    fallback_type: 'project_role',
    fallback_roles: 'developer'
  },
  condition_config: { field: 'review_result', routes: { failed: 'in_processing' }, routing_mode: 'automatic' },
  form_config: { fields: [{ field: 'review_result', label: '验证结果', type: 'select', options: [{ label: '不通过', value: 'failed' }] }] },
  validator_config: { type: 'requirement_terminal_gate' },
  ui_config: { button_type: 'warning', list_display: 'primary' },
  trigger_config: null,
  post_action_config: { type: 'notification', receiver: 'next_handler', title: '请重新处理' }
})

const draft = createAdvancedConfigDraft(source)
draft.form_config.fields[0].label = '已修改'
assert.equal(source.form_config.fields[0].label, '验证结果')
assert.equal(isAdvancedConfigDirty(source, draft), true)

applyAdvancedConfigDraft(source, draft)
assert.equal(source.form_config.fields[0].label, '已修改')
assert.equal(isAdvancedConfigDirty(source, createAdvancedConfigDraft(source)), false)
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```powershell
Set-Location frontend
npm test -- workflowAdvancedConfig
```

Expected: FAIL because `workflowAdvancedConfig.js` and its exported functions do not exist.

- [ ] **Step 3: Implement the draft boundary**

Export these constants and functions:

```js
export const ADVANCED_SECTION_KEYS = ['rules', 'assignment', 'form', 'button', 'notification']

const ADVANCED_KEYS = [
  'allowed_role_list',
  'handler_rule',
  'handler_target_roles',
  'handler_fallback_roles',
  'condition_config',
  'condition_routes',
  'form_config',
  'validator_config',
  'ui_config',
  'trigger_config',
  'post_action_config'
]

function clone(value) {
  return value === undefined ? undefined : structuredClone(value)
}

export function createAdvancedConfigDraft(transition) {
  return Object.fromEntries(ADVANCED_KEYS.map((key) => [key, clone(transition[key])]))
}

export function isAdvancedConfigDirty(transition, draft) {
  return JSON.stringify(createAdvancedConfigDraft(transition)) !== JSON.stringify(draft)
}

export function applyAdvancedConfigDraft(transition, draft) {
  for (const key of ADVANCED_KEYS) transition[key] = clone(draft[key])
  return transition
}
```

Use `structuredClone` because all workflow configuration values are JSON-compatible and the project targets a modern browser runtime.

- [ ] **Step 4: Extend serializer round-trip coverage**

Add a `route_dictionary: 'bug_type'` fixture and assert normalization plus serialization preserves it without adding static routes:

```js
const dictionarySource = {
  ...source,
  condition_config: { field: 'bug_type', route_dictionary: 'bug_type', routing_mode: 'automatic' }
}
const dictionaryRoundTrip = serializeWorkflowTransition(normalizeWorkflowTransition(dictionarySource))
assert.equal(dictionaryRoundTrip.condition_config.route_dictionary, 'bug_type')
assert.equal('routes' in dictionaryRoundTrip.condition_config, false)
```

- [ ] **Step 5: Verify Task 1**

Run:

```powershell
Set-Location frontend
npm test -- workflowAdvancedConfig workflowTransitionConfig
```

Expected: both utility suites pass.

### Task 2: Section State, Clearing, And Validation

**Files:**
- Modify: `frontend/src/utils/workflowAdvancedConfig.js`
- Modify: `frontend/src/utils/workflowAdvancedConfig.test.mjs`

- [ ] **Step 1: Write failing section-state tests**

Cover unconfigured, configured, and invalid states:

```js
assert.deepEqual(advancedSectionStates(emptyDraft, states), {
  rules: 'unconfigured',
  assignment: 'unconfigured',
  form: 'unconfigured',
  button: 'unconfigured',
  notification: 'unconfigured'
})

const invalid = createAdvancedConfigDraft(source)
invalid.form_config.fields.push({ field: 'review_result', label: '重复键', type: 'text', required: false })
invalid.post_action_config.title = ''
const result = validateAdvancedConfig(invalid, states)
assert.equal(result.valid, false)
assert.equal(result.firstSection, 'form')
assert.ok(result.errors.form.some((item) => item.code === 'duplicate_field_key'))
assert.ok(result.errors.notification.some((item) => item.code === 'notification_title_required'))
```

- [ ] **Step 2: Write failing clear-section tests**

Assert each section resets only its owned keys:

```js
const cleared = clearAdvancedSection(createAdvancedConfigDraft(source), 'notification')
assert.equal(cleared.trigger_config, null)
assert.equal(cleared.post_action_config, null)
assert.equal(cleared.form_config.fields.length, 1)

const clearedRules = clearAdvancedSection(createAdvancedConfigDraft(source), 'rules')
assert.deepEqual(clearedRules.condition_config, {})
assert.deepEqual(clearedRules.condition_routes, [])
assert.equal(clearedRules.validator_config, null)
assert.equal(clearedRules.handler_rule.target_type, 'previous_handler')
```

- [ ] **Step 3: Run tests and confirm failure**

Run:

```powershell
Set-Location frontend
npm test -- workflowAdvancedConfig
```

Expected: FAIL because section-state, clear, and validation functions are missing.

- [ ] **Step 4: Implement section ownership and validation**

Implement section clearing with explicit ownership:

```js
export function clearAdvancedSection(source, section) {
  const draft = structuredClone(source)
  if (section === 'rules') {
    draft.condition_config = {}
    draft.condition_routes = []
    draft.validator_config = null
  } else if (section === 'assignment') {
    draft.allowed_role_list = []
    draft.handler_rule = { target_type: 'keep_current', target_roles: '', fallback_type: 'keep_current', fallback_roles: '' }
    draft.handler_target_roles = []
    draft.handler_fallback_roles = []
  } else if (section === 'form') {
    draft.form_config = { fields: [] }
  } else if (section === 'button') {
    draft.ui_config = {}
  } else if (section === 'notification') {
    draft.trigger_config = null
    draft.post_action_config = null
  }
  return draft
}
```

Implement validation with one stable error collection per section:

```js
export function validateAdvancedConfig(draft, states) {
  const errors = Object.fromEntries(ADVANCED_SECTION_KEYS.map((key) => [key, []]))
  const add = (section, code, field, message) => errors[section].push({ code, field, message })
  const statusKeys = new Set(states.map((item) => item.status_key))
  const fields = draft.form_config?.fields || []
  const fieldKeys = fields.map((field) => String(field.field || '').trim())

  fields.forEach((field, index) => {
    const key = fieldKeys[index]
    if (!key) add('form', 'field_key_required', `form_config.fields.${index}.field`, '字段键不能为空')
    if (key && fieldKeys.indexOf(key) !== index) add('form', 'duplicate_field_key', `form_config.fields.${index}.field`, '字段键不能重复')
    if (field.type === 'select' && field.dictionary !== 'bug_type' && !(field.options || []).length && !String(field.option_lines || '').trim()) {
      add('form', 'select_options_required', `form_config.fields.${index}.options`, '下拉字段必须配置选项')
    }
  })

  const condition = draft.condition_config || {}
  const routes = draft.condition_routes || []
  if (condition.route_dictionary && routes.length) add('rules', 'dictionary_static_routes_conflict', 'condition_config.route_dictionary', '字典路由不能同时配置静态路由')
  if (routes.length && !String(condition.field || '').trim()) add('rules', 'route_field_required', 'condition_config.field', '请选择判断字段')
  if (condition.field && condition.route_dictionary !== 'bug_type' && !fieldKeys.includes(condition.field)) add('rules', 'route_field_missing', 'condition_config.field', '判断字段必须存在于动作表单')
  routes.forEach((route, index) => {
    if (!String(route.value || '').trim()) add('rules', 'route_value_required', `condition_routes.${index}.value`, '路由值不能为空')
    if (!statusKeys.has(route.status)) add('rules', 'route_status_invalid', `condition_routes.${index}.status`, '目标状态无效')
  })
  if (condition.routing_mode === 'automatic_with_override' && !(condition.allow_override_roles || []).length) {
    add('rules', 'override_roles_required', 'condition_config.allow_override_roles', '允许覆盖角色不能为空')
  }

  if (draft.handler_rule?.target_type === 'project_role' && !(draft.handler_target_roles || []).length) add('assignment', 'target_roles_required', 'handler_target_roles', '请选择目标角色')
  if (draft.handler_rule?.fallback_type === 'project_role' && !(draft.handler_fallback_roles || []).length) add('assignment', 'fallback_roles_required', 'handler_fallback_roles', '请选择回退角色')

  for (const [field, config] of [['trigger_config', draft.trigger_config], ['post_action_config', draft.post_action_config]]) {
    if (!config) continue
    if (!config.receiver) add('notification', 'notification_receiver_required', `${field}.receiver`, '请选择通知接收人')
    if (!String(config.title || '').trim()) add('notification', 'notification_title_required', `${field}.title`, '通知标题不能为空')
  }

  const firstSection = ADVANCED_SECTION_KEYS.find((key) => errors[key].length) || null
  return { valid: firstSection === null, errors, firstSection }
}
```

Implement configured-state calculation independently from validation:

```js
function isSectionConfigured(draft, section) {
  if (section === 'rules') return Boolean(Object.keys(draft.condition_config || {}).length || draft.condition_routes?.length || draft.validator_config)
  if (section === 'assignment') return Boolean(draft.allowed_role_list?.length || draft.handler_rule?.target_type !== 'keep_current' || draft.handler_rule?.fallback_type !== 'keep_current' || draft.handler_rule?.allow_manual_owner)
  if (section === 'form') return Boolean(draft.form_config?.title || draft.form_config?.submit_text || draft.form_config?.fields?.length)
  if (section === 'button') return Boolean(Object.keys(draft.ui_config || {}).length)
  return Boolean(draft.trigger_config || draft.post_action_config)
}

export function advancedSectionStates(draft, states) {
  const { errors } = validateAdvancedConfig(draft, states)
  return Object.fromEntries(ADVANCED_SECTION_KEYS.map((section) => [
    section,
    errors[section].length ? 'invalid' : isSectionConfigured(draft, section) ? 'configured' : 'unconfigured'
  ]))
}

export function configuredAdvancedSectionCount(draft, states) {
  return Object.values(advancedSectionStates(draft, states)).filter((value) => value !== 'unconfigured').length
}
```

Validation rules must be explicit:

- Form field keys are non-empty and unique.
- Select fields have `dictionary === 'bug_type'` or at least one complete option.
- Static routes require `condition_config.field`, non-empty value/status rows, and a status present in `states`.
- `route_dictionary` and static routes are mutually exclusive.
- A routing field must match a form field unless it is the `bug_type` dictionary route.
- `automatic_with_override` requires at least one override role.
- `project_role` handler sources require their corresponding role array.
- Enabled notification entries require receiver and non-empty title.

Return errors as stable objects, for example:

```js
{ code: 'duplicate_field_key', field: 'form_config.fields.1.field', message: '字段键不能重复' }
```

- [ ] **Step 5: Verify Task 2**

Run:

```powershell
Set-Location frontend
npm test -- workflowAdvancedConfig
```

Expected: section state, clearing, and validation tests pass.

### Task 3: Build The Overlay Drawer And Five Editors

**Files:**
- Create: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`
- Create: `frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`
- Modify: `frontend/src/utils/workflowAdvancedConfig.js`

- [ ] **Step 1: Write the drawer contract test**

Read the SFC as text and assert the stable user-facing and interaction contract:

```js
const source = await readFile(new URL('./WorkflowAdvancedConfigDrawer.vue', import.meta.url), 'utf8')
for (const label of ['流转规则', '处理人与权限', '动作表单', '按钮展示', '通知']) {
  assert.match(source, new RegExp(label))
}
assert.match(source, /<el-drawer/)
assert.match(source, /before-close="requestClose"/)
assert.match(source, /清空本页配置/)
assert.match(source, /取消/)
assert.match(source, /应用配置/)
assert.match(source, /未应用修改/)
```

- [ ] **Step 2: Run the contract test and confirm failure**

Run:

```powershell
Set-Location frontend
npm test -- workflowAdvancedConfigDrawer
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the drawer shell and lifecycle**

Define this component contract:

```js
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  transition: { type: Object, default: null },
  states: { type: Array, default: () => [] },
  roleOptions: { type: Array, default: () => [] },
  targetTypes: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue', 'apply'])
```

On closed-to-open transition, create a fresh isolated draft and reset the active section to `rules`. Implement `requestClose(done)` so clean drafts close immediately and dirty drafts call:

```js
await ElMessageBox.confirm('放弃未应用的修改？', '关闭高级配置', { type: 'warning' })
```

Expose a parent guard:

```js
defineExpose({
  hasPendingChanges: () => Boolean(draft.value && isAdvancedConfigDirty(props.transition, draft.value)),
  confirmDiscardPendingChanges
})
```

Use:

```vue
<el-drawer
  :model-value="modelValue"
  direction="rtl"
  :size="drawerSize"
  :before-close="requestClose"
  :append-to-body="false"
  modal-class="workflow-advanced-drawer-modal"
>
```

Set `drawerSize` to `clamp(520px, 42vw, 640px)`; the designer container must be the drawer positioning context so the overlay covers the canvas without changing its grid tracks.

- [ ] **Step 4: Implement the five section editors**

Move existing controls without changing stored keys:

- `rules`: `condition_config`, `condition_routes`, `validator_config`.
- `assignment`: `allowed_role_list`, `handler_rule`, `handler_target_roles`, `handler_fallback_roles`.
- `form`: `form_config.title`, `form_config.submit_text`, `form_config.fields`.
- `button`: `ui_config.button_type`, `list_display`, `action_category`, `visible_in_detail`, `visible_in_list`, `confirm_required`.
- `notification`: `trigger_config`, `post_action_config`.

For `route_dictionary === 'bug_type'`, render a read-only `Bug 类型字典自动路由` alert and hide static route editing. Do not delete the dictionary key.

- [ ] **Step 5: Implement section indicators and apply behavior**

Use `advancedSectionStates()` to render blue configured dots and red invalid dots. On apply:

```js
const result = validateAdvancedConfig(draft.value, props.states)
errors.value = result.errors
if (!result.valid) {
  activeSection.value = result.firstSection
  return
}
emit('apply', structuredClone(draft.value))
emit('update:modelValue', false)
```

The sticky footer contains `清空本页配置`, `取消`, and `应用配置`. `清空本页配置` must call `clearAdvancedSection()` for the active section only.

- [ ] **Step 6: Add restrained desktop styling**

Implement a drawer body with a fixed 150px section navigation and a scrollable editor. Use `grid-template-columns: repeat(auto-fit, minmax(190px, 1fr))` for form grids so they render as two columns when space permits and one column on narrower desktop windows. Keep header and footer fixed, use 8px-or-less radii, and ensure field rows have stable grid tracks. Do not add viewport-width font scaling, decorative gradients, or mobile acceptance rules.

- [ ] **Step 7: Verify Task 3**

Run:

```powershell
Set-Location frontend
npm test -- workflowAdvancedConfig workflowAdvancedConfigDrawer
npm run build
```

Expected: utility and drawer contract tests pass; Vite build succeeds.

### Task 4: Integrate The Drawer Into Workflow Designer

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`
- Modify: `frontend/src/utils/workflowTransitionConfig.test.mjs`

- [ ] **Step 1: Extend the contract test for designer integration**

Assert `WorkflowDesigner.vue` imports and renders the drawer, exposes an advanced entry, and no longer contains the old collapse:

```js
const designer = await readFile(new URL('./WorkflowDesigner.vue', import.meta.url), 'utf8')
assert.match(designer, /import WorkflowAdvancedConfigDrawer/)
assert.match(designer, /高级配置/)
assert.match(designer, /configuredAdvancedSectionCount/)
assert.doesNotMatch(designer, /workflow-advanced-config/)
assert.doesNotMatch(designer, /<el-collapse-item title="条件路由"/)
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

```powershell
Set-Location frontend
npm test -- workflowAdvancedConfigDrawer workflowTransitionConfig
```

Expected: FAIL because the designer still contains the old accordion and does not render the drawer.

- [ ] **Step 3: Reduce the right property panel to basic fields and summaries**

Keep editable action name/key, source status, target status, enabled state, and deletion. Replace editable role/handler controls with read-only summary rows and add:

```vue
<el-button type="primary" plain class="workflow-advanced-entry" @click="openAdvancedConfig">
  高级配置
  <span v-if="advancedConfigCount">已配置 {{ advancedConfigCount }} 项</span>
</el-button>
```

Do not remove state editing or graph toolbar behavior.

- [ ] **Step 4: Render and apply the drawer**

Add:

```vue
<WorkflowAdvancedConfigDrawer
  ref="advancedDrawerRef"
  v-model="advancedDrawerVisible"
  :transition="selectedTransition"
  :states="states"
  :role-options="roleOptions"
  :target-types="targetTypes"
  @apply="applyAdvancedConfig"
/>
```

Implement:

```js
function applyAdvancedConfig(draft) {
  if (!selectedTransition.value) return
  applyAdvancedConfigDraft(selectedTransition.value, draft)
}
```

Remove advanced mutation methods that moved into the drawer: `addConditionRoute`, `removeConditionRoute`, `addFormField`, `removeFormField`, `setValidator`, and `toggleAutomation`.

- [ ] **Step 5: Protect unsupported historical configuration**

If `unsupportedWorkflowConfigSections(selectedTransition)` is non-empty, the basic panel must show the existing warning and the advanced entry must open a read-only view or be disabled with a clear migration message. Preserve the existing final-save guard in `saveGraph()`.

- [ ] **Step 6: Add unsaved-draft guards**

Before applying a template, loading a different object type/configuration, or leaving the route, call the drawer's exposed confirmation function. Add `onBeforeRouteLeave` and `beforeunload` handling only while a draft is dirty. A canceled confirmation must abort the action and preserve the draft.

The guard helper should return a boolean:

```js
async function confirmAdvancedDraftCanClose() {
  if (!advancedDrawerRef.value?.hasPendingChanges()) return true
  return advancedDrawerRef.value.confirmDiscardPendingChanges()
}
```

- [ ] **Step 7: Verify Task 4**

Run:

```powershell
Set-Location frontend
npm test -- workflowAdvancedConfig workflowAdvancedConfigDrawer workflowTransitionConfig
npm run build
```

Expected: integration contract, serializer, and draft tests pass; production build succeeds.

### Task 5: Full Regression And Fixed Desktop Acceptance

**Files:**
- Modify: `frontend/scripts/verify-fixed-desktop.mjs`
- Test: all frontend utility and source-contract suites

- [ ] **Step 1: Add the workflow route to the fixed desktop smoke script**

Extend the existing route list with `/workflow` and make one process accept one fixed desktop size from environment variables:

```js
const viewport = {
  width: Number(process.env.SOAR_VIEWPORT_WIDTH || 1440),
  height: Number(process.env.SOAR_VIEWPORT_HEIGHT || 900),
  deviceScaleFactor: 1,
  mobile: false
}
const approvedDesktopSizes = new Set(['1366x768', '1440x900', '1920x1080'])
if (!approvedDesktopSizes.has(`${viewport.width}x${viewport.height}`)) {
  throw new Error(`Unsupported desktop viewport: ${viewport.width}x${viewport.height}`)
}
const routes = ['/', '/requirements', '/tasks', '/bugs', '/iterations', '/exception-rules', '/workflow']
```

Validate width and height against the approved desktop matrix and fail for unsupported values. Each process must call `Emulation.setDeviceMetricsOverride` exactly once; run a new process for the next desktop size.

- [ ] **Step 2: Run the complete frontend tests**

Run:

```powershell
Set-Location frontend
npm test
```

Expected: all `.test.mjs` files pass with zero failures.

- [ ] **Step 3: Run the production build**

Run:

```powershell
Set-Location frontend
npm run build
```

Expected: Vite build exits with code 0. Existing chunk-size warnings are allowed; compilation errors are not.

- [ ] **Step 4: Run fixed desktop smoke verification**

Start or reuse backend and frontend servers, provide a valid existing access token, and run three independent processes:

```powershell
Set-Location backend
$env:SOAR_ACCESS_TOKEN = python -c "from app.core.security import create_access_token; print(create_access_token('bob'))"
$env:SOAR_VIEWPORT_WIDTH = '1366'; $env:SOAR_VIEWPORT_HEIGHT = '768'; node ../frontend/scripts/verify-fixed-desktop.mjs
$env:SOAR_VIEWPORT_WIDTH = '1440'; $env:SOAR_VIEWPORT_HEIGHT = '900'; node ../frontend/scripts/verify-fixed-desktop.mjs
$env:SOAR_VIEWPORT_WIDTH = '1920'; $env:SOAR_VIEWPORT_HEIGHT = '1080'; node ../frontend/scripts/verify-fixed-desktop.mjs
```

Expected: each process reports its requested fixed viewport for every route, with `horizontalOverflow: false`, `loginVisible: false`, and `authError: false`.

- [ ] **Step 5: Perform fixed desktop drawer acceptance**

Repeat the drawer layout checks at `1366x768`, `1440x900`, and `1920x1080`. Keep each viewport unchanged for that run. Perform the full interaction sequence at `1440x900`, then repeat steps 2, 3, and the overlap/overflow checks at the other two sizes:

1. Open `/workflow`, select an assignee-rule configuration, and click a transition.
2. Record the selected transition's node positions and current canvas transform.
3. Open `高级配置`; verify the drawer overlays the right side and the recorded node positions/transform remain unchanged.
4. Edit each of the five sections, verify configured dots, and create one deliberate validation error to confirm red-dot navigation.
5. Verify `取消`, close, and Esc prompt before discarding dirty drafts.
6. Verify `应用配置` changes the selected transition but does not call the save API.
7. Click `保存流程图`, reload, and verify all five sections round-trip without field loss.
8. Open the default Bug classification transition and verify it shows dictionary routing without editable static type mappings.
9. Verify drawer width remains between 520px and 640px and form grids switch between one and two columns without truncated labels.

- [ ] **Step 6: Run repository integrity checks**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors. Review status to ensure no unrelated user changes were removed or reverted.

- [ ] **Step 7: Report completion**

Report:

- Actual modified and created files.
- Removal of the old inline advanced accordion and duplicate designer handlers.
- Exact frontend test, build, and fixed desktop results.
- Any residual risk, especially historical unsupported configuration and existing Vite bundle-size warnings.
