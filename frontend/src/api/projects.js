import { http } from './http'

export function fetchProjects() {
  return http.get('/projects')
}

export function createProject(payload) {
  return http.post('/projects', payload)
}
