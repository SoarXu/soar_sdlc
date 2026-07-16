import { http } from './http'

export function fetchUnassignedWorkItems() {
  return http.get('/work-items/unassigned')
}
