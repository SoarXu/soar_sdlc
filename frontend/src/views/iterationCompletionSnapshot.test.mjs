import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./IterationDetailView.vue', import.meta.url), 'utf8')

assert.match(source, /结束快照/)
assert.match(source, /completionSnapshot/)
assert.match(source, /snapshotCount\('requirement'/)
assert.match(source, /snapshotCount\('task'/)
assert.match(source, /snapshotCount\('test_run'/)
assert.match(source, /snapshotCount\('bug'/)
assert.match(source, /terminalCount\('requirement'/)
assert.match(source, /completionSnapshot\.value = detailRes\.data\.completion_snapshot \|\| null/)

console.log('iteration completion snapshot source contract passed')
