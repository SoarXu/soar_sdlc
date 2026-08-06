import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./IterationsView.vue', import.meta.url), 'utf8')

assert.match(source, /iterationFilters/)
assert.match(source, /placeholder="项目"/)
assert.match(source, /placeholder="状态"/)
assert.match(source, /filteredIterations/)
assert.match(source, /usePagination\(filteredIterations\)/)
assert.match(source, /iterationPage\.value = 1/)
assert.doesNotMatch(source, /placeholder="负责人"/)

console.log('iteration list filters contract passed')
