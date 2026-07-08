import { http } from './http'

export function fetchIterations(params) {
  return http.get('/iterations', { params })
}

export function fetchIterationDetail(id) {
  return http.get(`/iterations/${id}/detail`)
}

export function fetchAvailableIterationRequirements(id) {
  return http.get(`/iterations/${id}/available-requirements`)
}

export function linkIterationRequirements(id, requirementIds) {
  return http.post(`/iterations/${id}/requirements`, { requirement_ids: requirementIds })
}

export function unlinkIterationRequirement(id, requirementId) {
  return http.delete(`/iterations/${id}/requirements/${requirementId}`)
}

export function fetchAvailableIterationTasks(id) {
  return http.get(`/iterations/${id}/available-tasks`)
}

export function linkIterationTasks(id, taskIds) {
  return http.post(`/iterations/${id}/tasks`, { task_ids: taskIds })
}

export function unlinkIterationTask(id, taskId) {
  return http.delete(`/iterations/${id}/tasks/${taskId}`)
}

export function createIteration(payload) {
  return http.post('/iterations', payload)
}

export function updateIteration(id, payload) {
  return http.patch(`/iterations/${id}`, payload)
}

export function startIteration(id, payload = {}) {
  return http.post(`/iterations/${id}/start`, payload)
}

export function finishIteration(id, payload = {}) {
  return http.post(`/iterations/${id}/finish`, payload)
}

export function deferIterationWorkItems(id, payload) {
  return http.post(`/iterations/${id}/defer-work-items`, payload)
}

export function fetchIterationStatusOperations(id) {
  return http.get(`/iterations/${id}/status-operations`)
}

export function deleteIteration(id) {
  return http.delete(`/iterations/${id}`)
}
