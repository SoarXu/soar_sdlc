import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./TestsView.vue', import.meta.url), 'utf8')

assert.match(source, /caseFilters/)
assert.match(source, /runFilters/)
assert.match(source, /placeholder="搜索用例标题"/)
assert.match(source, /placeholder="搜索测试单名称"/)
assert.match(source, /filteredTestCases/)
assert.match(source, /filteredTestRuns/)
assert.match(source, /usePagination\(filteredTestCases\)/)
assert.match(source, /usePagination\(filteredTestRuns\)/)
assert.match(source, /casePage\.value = 1/)
assert.match(source, /runPage\.value = 1/)

console.log('test management filters contract passed')
