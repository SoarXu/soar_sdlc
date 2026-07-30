import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('../components/WorkflowActionButtons.vue', import.meta.url), 'utf8')

assert.equal(
  (source.match(/<slot name="after-primary" \/>/g) || []).length,
  1,
  '工作流操作组件只能渲染一次页面后置操作',
)

console.log('project action button deduplication contract passed')
