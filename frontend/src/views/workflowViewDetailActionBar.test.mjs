import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const viewPath = fileURLToPath(new URL('./WorkflowView.vue', import.meta.url))
const viewSource = await readFile(viewPath, 'utf8')

assert.match(
  viewSource,
  /<div class="page-actions workflow-detail-actions">[\s\S]*<div class="workflow-detail-actions__navigation">[\s\S]*返回后台管理[\s\S]*返回列表/
)
assert.match(
  viewSource,
  /<div class="workflow-detail-actions__editing">[\s\S]*(?:启用|停用)[\s\S]*(?:保存|创建方案)/
)
assert.match(
  viewSource,
  /\.workflow-detail-actions\s*\{[\s\S]*justify-content:\s*space-between/
)
assert.match(
  viewSource,
  /\.workflow-detail-actions__(?:navigation|editing)\s*\{[\s\S]*gap:\s*8px/
)
assert.match(
  viewSource,
  /@media \(max-width: 767px\)[\s\S]*\.workflow-detail-actions\s*\{[\s\S]*flex-wrap:\s*wrap/
)

console.log('workflow detail action bar layout source contract passed')
