import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const designerPath = fileURLToPath(new URL('./WorkflowDesigner.vue', import.meta.url))
const drawerPath = fileURLToPath(new URL('./WorkflowAdvancedConfigDrawer.vue', import.meta.url))
const designer = await readFile(designerPath, 'utf8')
const drawer = await readFile(drawerPath, 'utf8')

function functionBody(source, name, nextName) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `missing function ${name}`)
  const end = source.indexOf(`function ${nextName}(`, start)
  assert.notEqual(end, -1, `missing boundary function ${nextName}`)
  return source.slice(start, end)
}

assert.doesNotMatch(designer, />\s*新增流转\s*</)
assert.doesNotMatch(designer, /动作键/)
assert.doesNotMatch(designer, /class="workflow-config-panel"/)
assert.match(designer, /<WorkflowAdvancedConfigDrawer/)
assert.match(designer, /:state="drawerState"/)
assert.match(designer, /:transitions="transitions"/)
assert.match(designer, /@move-transition="moveTransition"/)
assert.match(designer, /@add-transition="addTransition"/)
assert.match(designer, /@back="returnToStateActions"/)
assert.match(designer, /disabled: !edge\.transition\.enabled/)

const saveGraphBody = functionBody(designer, 'saveGraph', 'addState')
assert.match(saveGraphBody, /advancedDrawer\.value\?\.applyPendingChanges\?\.\(\)/)
assert.ok(
  saveGraphBody.indexOf('applyPendingChanges') < saveGraphBody.indexOf('saving.value = true'),
  'the drawer draft must be applied before the save request starts'
)
assert.ok(
  saveGraphBody.indexOf('unsupportedWorkflowConfigSections') < saveGraphBody.indexOf('applyPendingChanges'),
  'unsupported historical configuration must block save before the drawer draft is reset'
)

assert.match(drawer, /主操作/)
assert.match(drawer, /更多操作/)
assert.match(drawer, /draggable="true"/)
assert.match(drawer, /emit\('move-transition'/)
assert.match(drawer, /emit\('add-transition'/)
assert.match(drawer, /emit\('select-transition'/)
assert.match(drawer, /emit\('back'/)
assert.doesNotMatch(drawer, /value: 'hidden'/)
assert.doesNotMatch(drawer, /visible_in_detail/)
assert.doesNotMatch(drawer, /visible_in_list/)
assert.match(drawer, /value: 'actual_start_date'/)
assert.match(drawer, /value: 'actual_end_date'/)
assert.match(drawer, /fields\[0\]\.field === 'effective_time'.*实际开始日期/)
assert.match(drawer, /fields\[0\]\.field === 'effective_time'.*实际完成日期/)

const applyPendingChangesBody = functionBody(drawer, 'applyPendingChanges', 'apply')
assert.match(applyPendingChangesBody, /if \(!draft\.value \|\| !props\.transition\) return true/)
assert.match(applyPendingChangesBody, /validateAdvancedConfig\(draft\.value, props\.states\)/)
assert.match(applyPendingChangesBody, /if \(!result\.valid\)[\s\S]*return false/)
assert.ok(
  applyPendingChangesBody.indexOf('validateAdvancedConfig') < applyPendingChangesBody.indexOf('hasPendingChanges'),
  'state-dependent validation must run before the dirty draft shortcut'
)
assert.match(applyPendingChangesBody, /if \(!hasPendingChanges\(\)\) return true/)
assert.match(applyPendingChangesBody, /emit\('apply', createAdvancedConfigDraft\(draft\.value\)\)/)
assert.match(applyPendingChangesBody, /initializeDraft\(\)[\s\S]*return true/)
assert.match(drawer, /defineExpose\(\{[^}]*applyPendingChanges/)

console.log('workflow designer drawer integration tests passed')
