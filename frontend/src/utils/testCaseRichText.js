import { sanitizeHtml } from './htmlSanitizer.js'

export function hasMeaningfulRichText(value) {
  const html = sanitizeHtml(value || '')
  const template = window.document.createElement('template')
  template.innerHTML = html
  if (template.content.querySelector('img,video,audio,canvas,table,hr')) return true
  return Boolean((template.content.textContent || '').replace(/\u00a0/g, ' ').trim())
}

export function legacyCaseStepsToRichHtml(value) {
  const rows = Array.isArray(value) ? value : []
  return rows.map((item, index) => {
    const step = plainTextToHtml(item?.step || '')
    const expected = plainTextToHtml(item?.expected || '')
    if (!step && !expected) return ''
    const number = index + 1
    return `<p><strong>步骤 ${number}</strong></p><div>${step}</div><p><strong>预期 ${number}</strong></p><div>${expected}</div>`
  }).join('')
}

export function displayedTestCaseSteps(testCase) {
  return hasMeaningfulRichText(testCase?.steps_content) ? sanitizeHtml(testCase.steps_content) : legacyCaseStepsToRichHtml(testCase?.steps_json)
}

export function testCaseExecutionRows(testCase) {
  if (hasMeaningfulRichText(testCase?.steps_content)) {
    return [{
      step: sanitizeHtml(testCase.steps_content),
      expected: sanitizeHtml(testCase.expected_result || ''),
      rich_content: true,
      result: 'passed',
      actual: ''
    }]
  }
  const rows = Array.isArray(testCase?.steps_json) && testCase.steps_json.length ? testCase.steps_json : [{ step: '', expected: '' }]
  return rows.map((item) => ({
    step: item?.step || '',
    expected: item?.expected || '',
    rich_content: false,
    result: 'passed',
    actual: ''
  }))
}

export function testCaseAuthoringPayload(caseForm) {
  const stepsContent = hasMeaningfulRichText(caseForm?.steps_content) ? sanitizeHtml(caseForm.steps_content) : null
  return { ...caseForm, steps_content: stepsContent, steps_json: null }
}

export function safeTestCaseHtml(value) {
  const html = sanitizeHtml(value || '')
  return hasMeaningfulRichText(html) ? html : '-'
}

export function safeExecutionCellHtml(value, richContent) {
  return richContent ? sanitizeHtml(value || '') : plainTextToHtml(value || '')
}

function plainTextToHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/\r?\n/g, '<br>')
}
