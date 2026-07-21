import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const componentPath = fileURLToPath(new URL('./WorkflowAdvancedConfigDrawer.vue', import.meta.url))
const source = await readFile(componentPath, 'utf8').catch(() => '')

assert.match(source, /<el-drawer\b/)
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

console.log('workflow advanced config drawer source-contract tests passed')
