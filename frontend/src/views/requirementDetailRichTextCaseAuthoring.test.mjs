import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./RequirementDetailView.vue', import.meta.url), 'utf8')

for (const field of ['precondition', 'steps_content', 'expected_result']) {
  const richTextEditor = new RegExp(
    `<RichTextPasteEditor\\b(?=[^>]*\\bv-model="caseForm\\.${field}")[^>]*\\/?>`,
    'u'
  )
  assert.match(source, richTextEditor, `RequirementDetailView should author ${field} with RichTextPasteEditor`)
}

const submitCase = source.match(
  /async function submitCase\(\) \{(?<body>[\s\S]*?)\r?\n\}\r?\nasync function openCaseExecution/u
)
assert.ok(submitCase, 'RequirementDetailView should define submitCase before openCaseExecution')

const payload = submitCase.groups.body.match(
  /const payload = \{(?<body>[\s\S]*?)\n\s*\}/u
)
assert.ok(payload, 'submitCase should build a payload before creating the test case')
assert.match(payload.groups.body, /^\s*\.\.\.testCaseAuthoringPayload\(caseForm\),/u)
assert.match(payload.groups.body, /project_id:/u)
assert.match(payload.groups.body, /requirement_id:/u)
assert.match(payload.groups.body, /default_tester_id:/u)
assert.match(submitCase.groups.body, /await createTestCase\(payload\)/u)
assert.doesNotMatch(
  payload.groups.body,
  /\.\.\.caseForm|steps_content:|steps_json:|precondition:|expected_result:/u,
  'submitCase must not override sanitized rich-text fields after building the shared payload'
)
assert.doesNotMatch(source, /caseForm\.steps_json/u)

console.log('requirement detail rich-text case authoring contracts passed')
