import { http } from './http'

export function fetchProjects() {
  return http.get('/projects')
}

export function createProject(payload) {
  return http.post('/projects', payload)
}

export function updateProject(id, payload) {
  return http.patch(`/projects/${id}`, payload)
}

export function deleteProject(id) {
  return http.delete(`/projects/${id}`)
}
