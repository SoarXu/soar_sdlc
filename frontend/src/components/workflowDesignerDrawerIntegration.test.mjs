import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const designerPath = fileURLToPath(new URL('./WorkflowDesigner.vue', import.meta.url))
const drawerPath = fileURLToPath(new URL('./WorkflowAdvancedConfigDrawer.vue', import.meta.url))
const designer = await readFile(designerPath, 'utf8')
const drawer = await readFile(drawerPath, 'utf8')

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

console.log('workflow designer drawer integration tests passed')
