import { http } from './http'

export function fetchTestCases() {
  return http.get('/test-cases')
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
