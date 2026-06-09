import { http } from './http'

export function fetchBugs() {
  return http.get('/bugs')
}

export function createBug(payload) {
  return http.post('/bugs', payload)
}

export function updateBug(id, payload) {
  return http.patch(`/bugs/${id}`, payload)
}

export function deleteBug(id) {
  return http.delete(`/bugs/${id}`)
}
