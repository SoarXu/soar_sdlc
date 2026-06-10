import { http } from './http'

export function fetchProjects() {
  return http.get('/projects')
}

export function fetchProject(id) {
  return http.get(`/projects/${id}`)
}

export function createProject(payload) {
  return http.post('/projects', payload)
}

export function updateProject(id, payload) {
  return http.patch(`/projects/${id}`, payload)
}

export function fetchProjectStatusOperations(id) {
  return http.get(`/projects/${id}/status-operations`)
}

export function startProject(id, payload = {}) {
  return http.post(`/projects/${id}/start`, payload)
}

export function suspendProject(id, payload = {}) {
  return http.post(`/projects/${id}/suspend`, payload)
}

export function closeProject(id, payload = {}) {
  return http.post(`/projects/${id}/close`, payload)
}

export function activateProject(id, payload = {}) {
  return http.post(`/projects/${id}/activate`, payload)
}

export function deleteProject(id) {
  return http.delete(`/projects/${id}`)
}
