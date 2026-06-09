import { http } from './http'

export function fetchIterations() {
  return http.get('/iterations')
}

export function createIteration(payload) {
  return http.post('/iterations', payload)
}

export function updateIteration(id, payload) {
  return http.patch(`/iterations/${id}`, payload)
}

export function deleteIteration(id) {
  return http.delete(`/iterations/${id}`)
}
