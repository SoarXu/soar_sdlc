import assert from 'node:assert/strict'
import { JSDOM } from 'jsdom'

globalThis.window = new JSDOM('<!doctype html><html><body></body></html>').window

const {
  hasMeaningfulRichText,
  displayedTestCaseSteps,
  legacyCaseStepsToRichHtml,
  safeExecutionCellHtml,
  safeTestCaseHtml,
  testCaseAuthoringPayload,
  testCaseExecutionRows
} = await import('./testCaseRichText.js')

assert.equal(
  legacyCaseStepsToRichHtml([
    { step: '<打开>\n登录页', expected: '显示 & 登录表单' },
    { step: '提交账号', expected: '进入首页' }
  ]),
  '<p><strong>步骤 1</strong></p><div>&lt;打开&gt;<br>登录页</div><p><strong>预期 1</strong></p><div>显示 &amp; 登录表单</div><p><strong>步骤 2</strong></p><div>提交账号</div><p><strong>预期 2</strong></p><div>进入首页</div>'
)

for (const blank of ['', '  ', '<p><br></p>', '<div><br></div>', '<p>&nbsp;</p>']) {
  assert.equal(hasMeaningfulRichText(blank), false, `${blank} must be treated as empty editor HTML`)
}
assert.equal(hasMeaningfulRichText('<img src="data:image/png;base64,AA==">'), true)

assert.deepEqual(testCaseExecutionRows({
  steps_content: '<p>整块步骤</p>',
  expected_result: '<p>整体预期</p>',
  steps_json: [{ step: 'legacy', expected: 'legacy expected' }]
}), [{ step: '<p>整块步骤</p>', expected: '<p>整体预期</p>', rich_content: true, result: 'passed', actual: '' }])
assert.deepEqual(testCaseExecutionRows({
  steps_content: '<p><br></p>',
  steps_json: [{ step: 'legacy', expected: 'legacy expected' }]
}), [{ step: 'legacy', expected: 'legacy expected', rich_content: false, result: 'passed', actual: '' }])

assert.equal(safeTestCaseHtml('<p onclick="bad()">内容</p><script>alert(1)</script>'), '<p>内容</p>')
assert.equal(safeTestCaseHtml('<a href="&#x6a;avascript:alert(1)">链接</a>'), '<a>链接</a>')
assert.equal(safeTestCaseHtml('<svg><a xlink:href="javascript:alert(1)">x</a></svg>'), '-')
assert.equal(safeTestCaseHtml('<img src=x onerror=alert(1)//>'), '<img src="x">')
assert.equal(safeTestCaseHtml(''), '-')
assert.equal(safeExecutionCellHtml('<b>legacy</b>', false), '&lt;b&gt;legacy&lt;/b&gt;')
assert.equal(safeExecutionCellHtml('<b>rich</b>', true), '<b>rich</b>')

const legacyEditHtml = legacyCaseStepsToRichHtml([{ step: '旧步骤', expected: '旧预期' }])
const clearedPayload = testCaseAuthoringPayload({ title: 'legacy', steps_content: '' })
assert.equal(legacyEditHtml.includes('旧步骤'), true)
assert.equal(clearedPayload.steps_content, null)
assert.equal(clearedPayload.steps_json, null)
assert.equal(displayedTestCaseSteps(clearedPayload), '')

console.log('test-case rich-text conversion contracts passed')
