import { http } from './http'

export function fetchIterations(params) {
  return http.get('/iterations', { params })
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
