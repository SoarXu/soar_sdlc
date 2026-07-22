import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./IterationDetailView.vue', import.meta.url), 'utf8')

assert.match(source, /detailRes\.data\.historical_bugs/)
assert.match(source, /后续已重新激活/)
assert.match(source, /status_name_at_leave/)
assert.match(source, /current_iteration_id/)

console.log('iteration historical Bug source contract passed')
