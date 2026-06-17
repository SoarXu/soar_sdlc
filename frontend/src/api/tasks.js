import { http } from './http'

export function fetchTasks() {
  return http.get('/tasks')
}

export function fetchTask(id) {
  return http.get(`/tasks/${id}`)
}

export function createTask(payload) {
  return http.post('/tasks', payload)
}

export function updateTask(id, payload) {
  return http.patch(`/tasks/${id}`, payload)
}

export function activateTask(id) {
  return http.post(`/tasks/${id}/activate`)
}

export function closeTask(id, payload) {
  return http.post(`/tasks/${id}/close`, payload)
}

export function completeTask(id) {
  return http.post(`/tasks/${id}/complete`)
}

export function fetchTaskStatusOperations(id) {
  return http.get(`/tasks/${id}/status-operations`)
}

export function fetchTaskAuditLogs(id) {
  return http.get(`/tasks/${id}/audit-logs`)
}

export function deleteTask(id) {
  return http.delete(`/tasks/${id}`)
}
