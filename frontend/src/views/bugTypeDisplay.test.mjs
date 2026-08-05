import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const projectDetail = await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')
const iterationDetail = await readFile(new URL('./IterationDetailView.vue', import.meta.url), 'utf8')
const bugDetail = await readFile(new URL('./BugDetailView.vue', import.meta.url), 'utf8')

assert.match(projectDetail, /const \{ bugTypeOptions, bugTypeLabel \} = useBugTypes\(\)/)
assert.match(projectDetail, /<el-table-column label="Bug 类型"[^>]*><template #default="\{ row \}">\{\{ bugTypeLabel\(row\.bug_type\) \}\}<\/template><\/el-table-column>/)
assert.match(iterationDetail, /const \{ bugTypeOptions, bugTypeLabel \} = useBugTypes\(\)/)
assert.match(iterationDetail, /<el-table-column label="Bug 类型"[^>]*><template #default="\{ row \}">\{\{ bugTypeLabel\(row\.bug_type\) \}\}<\/template><\/el-table-column>/)
assert.match(bugDetail, /const \{ bugTypeOptions, bugTypeLabel \} = useBugTypes\(\)/)
assert.match(bugDetail, /<el-descriptions-item label="Bug 类型">\{\{ bugTypeLabel\(bug\.bug_type\) \}\}<\/el-descriptions-item>/)
