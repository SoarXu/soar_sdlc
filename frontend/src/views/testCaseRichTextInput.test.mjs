import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const normalize = (source) => source.replace(/\r\n/g, '\n')
const projectDetail = normalize(await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8'))
const caseDetail = normalize(await readFile(new URL('./TestCaseDetailView.vue', import.meta.url), 'utf8'))

for (const [name, source] of [['project detail', projectDetail], ['test-case detail', caseDetail]]) {
  assert.match(source, /<RichTextPasteEditor v-model="caseForm\.precondition"/u, `${name} must edit preconditions as rich text`)
  assert.match(source, /<RichTextPasteEditor v-model="caseForm\.steps_content"/u, `${name} must edit the whole case procedure as rich text`)
  assert.match(source, /<RichTextPasteEditor v-model="caseForm\.expected_result"/u, `${name} must edit the overall expected result as rich text`)
  assert.doesNotMatch(source, /<el-table :data="caseForm\.steps_json"/u, `${name} must not author cases as step rows`)
  assert.doesNotMatch(source, /addCaseStep|removeCaseStep/u, `${name} must not expose add/remove-step controls`)
}

assert.match(caseDetail, /v-html="safeTestCaseHtml\(testCase\.precondition\)"/u)
assert.match(caseDetail, /v-html="safeTestCaseHtml\(displayedStepsContent\)"/u)
assert.match(caseDetail, /v-html="safeTestCaseHtml\(testCase\.expected_result\)"/u)

assert.match(projectDetail, /testCaseAuthoringPayload\(caseForm\)/u)
assert.match(caseDetail, /testCaseAuthoringPayload\(caseForm\)/u)

for (const relativePath of ['./ProjectDetailView.vue', './DashboardView.vue', './IterationDetailView.vue', './BugDetailView.vue', './TestsView.vue', './RequirementDetailView.vue']) {
  const source = normalize(await readFile(new URL(relativePath, import.meta.url), 'utf8'))
  assert.match(source, /testCaseExecutionRows\(/u, `${relativePath} must use the rich/legacy execution adapter`)
  assert.match(source, /safeExecutionCellHtml\(/u, `${relativePath} must render execution cells safely`)
}

console.log('test-case rich-text authoring contracts passed')
