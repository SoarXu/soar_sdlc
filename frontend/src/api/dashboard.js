import { http } from './http'

export function fetchWorkbench(params = {}) {
  return http.get('/dashboard/workbench', { params })
}

export function fetchWorkbenchItems(params = {}) {
  return http.get('/dashboard/workbench/items', {
    params,
    paramsSerializer: { indexes: null }
  })
}
