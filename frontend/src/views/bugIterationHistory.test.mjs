import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./BugDetailView.vue', import.meta.url), 'utf8')

assert.match(source, /bug\.iteration_history/)
assert.match(source, /迭代轨迹/)
assert.match(source, /status_name_at_leave/)
assert.match(source, /enter_reason/)

console.log('Bug iteration history source contract passed')
