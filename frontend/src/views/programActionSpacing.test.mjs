import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const [styles, workflowButtons] = await Promise.all([
  readFile(new URL('../styles.css', import.meta.url), 'utf8'),
  readFile(new URL('../components/WorkflowActionButtons.vue', import.meta.url), 'utf8'),
])

assert.match(
  styles,
  /\.project-list-actions\s*\{[\s\S]*?--workflow-action-gap:\s*6px;[\s\S]*?gap:\s*var\(--workflow-action-gap\);/,
  '项目集列表必须为直接按钮和工作流按钮提供同一 6px 间距规则',
)
assert.match(workflowButtons, /\.workflow-action-buttons\s*\{[\s\S]*?gap:\s*var\(--workflow-action-gap,\s*8px\);/)
assert.match(workflowButtons, /\.workflow-primary-actions\s*\{[\s\S]*?gap:\s*var\(--workflow-action-gap,\s*4px\);/)

console.log('program action spacing contract passed')
