import { http } from './http'

export function fetchDashboardSummary() {
  return http.get('/dashboard/summary')
}

export function fetchWorkbench(params = {}) {
  return http.get('/dashboard/workbench', { params })
}

export function moveWorkbenchItem(payload) {
  return http.post('/dashboard/workbench/move', payload)
}
