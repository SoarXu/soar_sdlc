import { http } from './http'

export function fetchRequirements() {
  return http.get('/requirements')
}

export function fetchRequirement(id) {
  return http.get(`/requirements/${id}`)
}

export function createRequirement(payload) {
  return http.post('/requirements', payload)
}

export function updateRequirement(id, payload) {
  return http.patch(`/requirements/${id}`, payload)
}

export function activateRequirement(id) {
  return http.post(`/requirements/${id}/activate`)
}

export function closeRequirement(id, payload) {
  return http.post(`/requirements/${id}/close`, payload)
}

export function completeRequirement(id) {
  return http.post(`/requirements/${id}/complete`)
}

export function fetchRequirementStatusOperations(id) {
  return http.get(`/requirements/${id}/status-operations`)
}

export function fetchRequirementAuditLogs(id) {
  return http.get(`/requirements/${id}/audit-logs`)
}

export function deleteRequirement(id) {
  return http.delete(`/requirements/${id}`)
}

export function generateTask(requirementId, payload) {
  return http.post(`/requirements/${requirementId}/generate-task`, payload)
}
