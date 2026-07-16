import { http } from './http'

export function fetchBugTypes(params = {}) {
  return http.get('/bug-types', { params })
}
