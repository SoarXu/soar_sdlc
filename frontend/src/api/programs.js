import { http } from './http'

export function fetchPrograms() {
  return http.get('/programs')
}

export function createProgram(payload) {
  return http.post('/programs', payload)
}

export function updateProgram(id, payload) {
  return http.patch(`/programs/${id}`, payload)
}

export function deleteProgram(id) {
  return http.delete(`/programs/${id}`)
}
