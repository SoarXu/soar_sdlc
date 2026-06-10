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

export function startProject(id) {
  return http.post(`/projects/${id}/start`)
}

export function suspendProject(id) {
  return http.post(`/projects/${id}/suspend`)
}

export function closeProject(id) {
  return http.post(`/projects/${id}/close`)
}

export function activateProject(id) {
  return http.post(`/projects/${id}/activate`)
}

export function deleteProject(id) {
  return http.delete(`/projects/${id}`)
}
