import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./IterationDetailView.vue', import.meta.url), 'utf8')

assert.match(
  source,
  /requirementOperationWidth\s*=\s*computed\(\(\) => workflowActionColumnWidth\([\s\S]*?\{ minWidth: 300, extraWidth: 340 \}[\s\S]*?\)\)/,
  '迭代需求操作列必须为编辑、工作流动作、生成任务、建用例、删除和移除预留完整的单行空间',
)

console.log('iteration requirement action column width contract passed')
