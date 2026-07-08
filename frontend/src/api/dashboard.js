import { http } from './http'

export function fetchWorkbench(params = {}) {
  return http.get('/dashboard/workbench', { params })
}
