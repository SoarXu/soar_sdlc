import { http } from './http'

export function fetchTestRuns() {
  return http.get('/test-runs')
}

export function createTestRun(payload) {
  return http.post('/test-runs', payload)
}

export function updateTestRun(id, payload) {
  return http.patch(`/test-runs/${id}`, payload)
}

export function deleteTestRun(id) {
  return http.delete(`/test-runs/${id}`)
}

export function selectTestCases(testRunId, payload) {
  return http.post(`/test-runs/${testRunId}/cases`, payload)
}

export function updateTestRunCase(id, payload) {
  return http.patch(`/test-run-cases/${id}`, payload)
}

export function fetchTestRunCases() {
  return http.get('/test-run-cases')
}

export function createBugFromTestRunCase(id, payload) {
  return http.post(`/test-run-cases/${id}/bugs`, payload)
}
