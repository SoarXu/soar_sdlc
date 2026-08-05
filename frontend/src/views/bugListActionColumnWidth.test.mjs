import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const bugsView = await readFile(new URL('./BugsView.vue', import.meta.url), 'utf8')

assert.match(
  bugsView,
  /workflowActionColumnWidth\(\s*pagedBugs\.value\.map\(\(row\) => workflowTransitionsFor\(row\)\),\s*\{ minWidth: 240, extraWidth: 160 \}\s*\)/,
  'Bug 操作列必须为关注、工作流动作、更多和删除预留完整的单行空间',
)

console.log('bug list action column width contract passed')
