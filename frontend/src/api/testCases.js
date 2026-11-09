import { http } from './http'

export function fetchTestCases() {
  return http.get('/test-cases')
}

export function downloadTestCaseImportTemplate(projectId) {
  return http.get('/test-cases/import/template', { params: { project_id: projectId }, responseType: 'blob', timeout: 60000 })
}

function testCaseImportForm(file, options) {
  const form = new FormData()
  form.append('file', file)
  form.append('project_id', options.projectId)
  if (options.defaultRequirementId) form.append('default_requirement_id', options.defaultRequirementId)
  form.append('requirement_overrides', JSON.stringify(options.overrides || {}))
  form.append('duplicate_strategy', options.duplicateStrategy || 'skip')
  return form
}

export function previewTestCaseImport(file, options) {
  return http.post('/test-cases/import/preview', testCaseImportForm(file, options), { timeout: 60000 })
}

export function commitTestCaseImport(file, options) {
  return http.post('/test-cases/import/commit', testCaseImportForm(file, options), { timeout: 60000 })
}

export function fetchTestCase(id) {
  return http.get(`/test-cases/${id}`)
}

export function createTestCase(payload) {
  return http.post('/test-cases', payload)
}

export function updateTestCase(id, payload) {
  return http.patch(`/test-cases/${id}`, payload)
}

export function deleteTestCase(id) {
  return http.delete(`/test-cases/${id}`)
}

export function executeTestCase(id, payload) {
  return http.post(`/test-cases/${id}/executions`, payload)
}

export function fetchTestCaseExecutions(id) {
  return http.get(`/test-cases/${id}/executions`)
}

export function createBugFromTestCase(id, payload) {
  return http.post(`/test-cases/${id}/bugs`, payload)
}
