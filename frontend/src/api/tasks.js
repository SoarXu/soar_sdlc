import { http } from './http'

export function fetchTasks() {
  return http.get('/tasks')
}

export function createTask(payload) {
  return http.post('/tasks', payload)
}

export function updateTask(id, payload) {
  return http.patch(`/tasks/${id}`, payload)
}

export function deleteTask(id) {
  return http.delete(`/tasks/${id}`)
}
