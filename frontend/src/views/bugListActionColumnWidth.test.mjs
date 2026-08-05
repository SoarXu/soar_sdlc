import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const bugsView = await readFile(new URL('./BugsView.vue', import.meta.url), 'utf8')

assert.doesNotMatch(
  bugsView,
  /WatchToggleButton/,
  '全局 Bug 列表不应渲染关注控件',
)

assert.match(
  bugsView,
  /workflowActionColumnWidth\(\s*pagedBugs\.value\.map\(\(row\) => workflowTransitionsFor\(row\)\),\s*\{ minWidth: 180, extraWidth: 90 \}\s*\)/,
  'Bug 操作列应为工作流动作、更多和删除预留完整的单行空间',
)

console.log('bug list action column width contract passed')
