import { http } from './http'

export function fetchUnassignedWorkItems() {
  return http.get('/work-items/unassigned')
}

export function claimWorkItem(objectType, id, payload = {}) {
  return http.post(`/work-items/${objectType}/${id}/claim`, payload)
}

export function assignWorkItem(objectType, id, payload) {
  return http.post(`/work-items/${objectType}/${id}/assign`, payload)
}

export function batchAssignWorkItems(payload) {
  return http.post('/work-items/batch-assign', payload)
}

export function autoAssignWorkItems(payload = {}) {
  return http.post('/work-items/unassigned/auto-assign', payload)
}
