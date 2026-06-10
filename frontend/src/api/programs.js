import { http } from './http'

export function fetchPrograms() {
  return http.get('/programs')
}

export function fetchProgramTree() {
  return http.get('/programs/tree')
}

export function fetchProgramStatusOptions() {
  return http.get('/programs/status-options')
}

export function createProgram(payload) {
  return http.post('/programs', payload)
}

export function updateProgram(id, payload) {
  return http.patch(`/programs/${id}`, payload)
}

export function fetchProgramStatusOperations(id) {
  return http.get(`/programs/${id}/status-operations`)
}

export function startProgram(id, payload = {}) {
  return http.post(`/programs/${id}/start`, payload)
}

export function suspendProgram(id, payload = {}) {
  return http.post(`/programs/${id}/suspend`, payload)
}

export function closeProgram(id, payload = {}) {
  return http.post(`/programs/${id}/close`, payload)
}

export function activateProgram(id, payload = {}) {
  return http.post(`/programs/${id}/activate`, payload)
}

export function deleteProgram(id) {
  return http.delete(`/programs/${id}`)
}
