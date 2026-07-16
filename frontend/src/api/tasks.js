import { http } from './http'
import { toWorkItemPatchPayload } from '../utils/workItemPatchPayload'

export function fetchTasks() {
  return http.get('/tasks')
}

export function fetchTask(id) {
  return http.get(`/tasks/${id}`)
}

export function createTask(payload) {
  return http.post('/tasks', payload)
}

export function createLinkedTask(payload) {
  return http.post('/tasks/linked', payload)
}

export function updateTask(id, payload) {
  return http.patch(`/tasks/${id}`, toWorkItemPatchPayload(payload))
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
