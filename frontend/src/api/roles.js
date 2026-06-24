import { http } from './http'

export function fetchRoles() {
  return http.get('/roles')
}

export function createRole(data) {
  return http.post('/roles', data)
}

export function updateRole(id, data) {
  return http.put(`/roles/${id}`, data)
}

export function deleteRole(id) {
  return http.delete(`/roles/${id}`)
}
