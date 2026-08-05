import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./DashboardView.vue', import.meta.url), 'utf8')

assert.match(source, /const itemTypes = \[\s*\{ label: '需求', value: 'requirement' \},\s*\{ label: '任务', value: 'task' \},\s*\{ label: 'Bug', value: 'bug' \}\s*\]/)
assert.doesNotMatch(source, /\{ label: '测试用例', value: 'test_case' \}/)
assert.doesNotMatch(source, /\{ label: '测试单', value: 'test_run' \}/)

console.log('dashboard workbench type filter contract passed')
