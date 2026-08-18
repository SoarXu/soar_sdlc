import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const [tasksView, bugsView, styles] = await Promise.all([
  readFile(new URL('./TasksView.vue', import.meta.url), 'utf8'),
  readFile(new URL('./BugsView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../styles.css', import.meta.url), 'utf8')
])

for (const [name, source] of [['任务', tasksView], ['Bug', bugsView]]) {
  assert.match(
    source,
    /<div class="table-actions work-item-list-actions">[\s\S]*?<WorkflowActionButtons[\s\S]*?<el-popconfirm[\s\S]*?<\/div>/,
    `${name} 列表的工作流和删除操作应放入同一对齐容器`,
  )
  assert.match(
    source,
    /workflowActionColumnWidth\([\s\S]*?\{ minWidth: 180, extraWidth: 90 \}[\s\S]*?\)/,
    `${name} 操作列应采用统一的宽度计算规则`,
  )
}

assert.match(
  styles,
  /\.work-item-list-actions\s*\{[\s\S]*?min-height:\s*32px;[\s\S]*?align-items:\s*center;[\s\S]*?\}/,
  '任务和 Bug 列表操作区应统一为 32px 高度并垂直居中',
)
assert.match(
  styles,
  /\.work-item-list-actions\s+\.el-button\s*\{[\s\S]*?min-height:\s*32px;[\s\S]*?\}/,
  '任务和 Bug 的操作按钮应保持相同的最小点击高度',
)

console.log('task and bug list action presentation contract passed')
