import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const componentPath = fileURLToPath(new URL('./WorkflowAdvancedConfigDrawer.vue', import.meta.url))
const source = await readFile(componentPath, 'utf8').catch(() => '')

assert.match(
  source,
  /<div class="drawer-header__leading">[\s\S]*?<el-button v-if="transition"[\s\S]*?<div>[\s\S]*?<h2>/
)
assert.match(
  source,
  /\.drawer-header\s*\{[^}]*justify-content:\s*flex-start/s
)

assert.match(source, /<el-drawer\b/)
assert.match(
  source,
  /<el-dialog[\s\S]*?v-model="discardConfirmVisible"[\s\S]*?取消[\s\S]*?放弃修改[\s\S]*?应用并关闭/
)
assert.match(source, /function applyPendingChangesAndContinue\(\)/)
for (const label of ['流转规则', '处理人与权限', '动作表单', '按钮展示', '通知']) {
  assert.match(source, new RegExp(label))
}
assert.match(source, /requestClose/)
for (const label of ['清空本页配置', '取消', '应用配置', '未应用修改']) {
  assert.match(source, new RegExp(label))
}
assert.match(source, /\.form-grid :deep\(\.el-form-item\)\s*\{[^}]*display:\s*block/s)
assert.match(source, /\.form-grid :deep\(\.el-form-item__content\)\s*\{[^}]*width:\s*100%/s)
assert.match(source, /:max-collapse-tags="2"/)
assert.match(source, /collapse-tags-tooltip/)
assert.match(source, /画布布线/)
assert.match(source, /手工布线/)
assert.match(source, /恢复自动布线/)
assert.match(source, /reset-diagram-route/)
assert.match(source, /isManualDiagramRoute\(transition\.diagram_config\)\s*\?[^:]+:/)
assert.match(source, /v-if="isManualDiagramRoute\(transition\.diagram_config\)"/)
assert.match(source, /watch\(\(\) => props\.state\?\.category,\s*\(category\) => \{\s*if \(category !== 'terminal' && props\.state\) props\.state\.terminal_kind = null/s)
assert.match(source, /v-if="state\.category === 'terminal'" label="终态归类"[\s\S]*?<el-select v-model="state\.terminal_kind" :clearable="false"[^>]*required/s)
assert.match(source, /<el-form-item v-if="state\.category === 'terminal'" label="终态归类" :error="stateErrorFor\('terminal_kind'\)"/)
assert.match(source, /const stateValidation = validateWorkflowState\(props\.state\)[\s\S]*?if \(!stateValidation\.valid\) return false/)
assert.ok(
  source.indexOf('validateWorkflowState(props.state)') < source.indexOf('if (!draft.value || !props.transition) return true'),
  'state validation must run before the transition-draft early return'
)

console.log('workflow advanced config drawer source-contract tests passed')
