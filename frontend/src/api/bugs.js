import { http } from './http'

export function fetchBugs() {
  return http.get('/bugs')
}

export function fetchBug(id) {
  return http.get(`/bugs/${id}`)
}

export function fetchBugValidationContext(id) {
  return http.get(`/bugs/${id}/validation-context`)
}

export function fetchBugStatusOperations(id) {
  return http.get(`/bugs/${id}/status-operations`)
}

export function createBug(payload) {
  return http.post('/bugs', payload)
}

export function updateBug(id, payload) {
  return http.patch(`/bugs/${id}`, payload)
}

export function assignBug(id, payload) {
  return http.post(`/bugs/${id}/assign`, payload)
}

export function batchAssignBugs(payload) {
  return http.post('/bugs/batch-assign', payload)
}

export function startFixingBug(id, payload) {
  return http.post(`/bugs/${id}/start-fixing`, payload)
}

export function resolveBug(id, payload) {
  return http.post(`/bugs/${id}/resolve`, payload)
}

export function verifyBugPassed(id, payload) {
  return http.post(`/bugs/${id}/verify-passed`, payload)
}

export function verifyBugFailed(id, payload) {
  return http.post(`/bugs/${id}/verify-failed`, payload)
}

export function suspendBug(id, payload) {
  return http.post(`/bugs/${id}/suspend`, payload)
}

export function closeBug(id, payload) {
  return http.post(`/bugs/${id}/close`, payload)
}

export function activateBug(id, payload) {
  return http.post(`/bugs/${id}/activate`, payload)
}

export function deleteBug(id) {
  return http.delete(`/bugs/${id}`)
}
