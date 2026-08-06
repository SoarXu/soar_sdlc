import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./BugsView.vue', import.meta.url), 'utf8')

assert.match(source, /bugFilters/)
assert.match(source, /placeholder="项目"/)
assert.match(source, /placeholder="严重程度"/)
assert.match(source, /placeholder="状态"/)
assert.match(source, /filteredBugs/)
assert.match(source, /usePagination\(filteredBugs\)/)
assert.match(source, /bugPage\.value = 1/)
assert.doesNotMatch(source, /placeholder="当前处理人"/)

console.log('bug list filters contract passed')
