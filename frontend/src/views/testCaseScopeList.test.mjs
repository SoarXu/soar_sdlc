import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

for (const path of ['ProjectDetailView.vue', 'TestsView.vue', 'TestCaseDetailView.vue', 'RequirementDetailView.vue']) {
  const source = readFileSync(new URL(`./${path}`, import.meta.url), 'utf8')
  assert.match(source, /v-model="caseForm\.test_scopes"[^>]*multiple/u, path)
  assert.match(source, /test_scopes/u, path)
}

const testCasesView = readFileSync(new URL('./TestsView.vue', import.meta.url), 'utf8')
assert.match(testCasesView, /v-model="caseFilters\.scopes"[^>]*multiple/u)
assert.match(testCasesView, /caseFilters\.scopes\.some/u)

console.log('test-case scope list UI contracts passed')
