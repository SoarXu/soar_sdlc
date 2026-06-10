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

export function startProgram(id) {
  return http.post(`/programs/${id}/start`)
}

export function suspendProgram(id) {
  return http.post(`/programs/${id}/suspend`)
}

export function closeProgram(id) {
  return http.post(`/programs/${id}/close`)
}

export function activateProgram(id) {
  return http.post(`/programs/${id}/activate`)
}

export function deleteProgram(id) {
  return http.delete(`/programs/${id}`)
}
