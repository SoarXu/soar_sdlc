import { http } from './http'

export function fetchVersionInfo() {
  return http.get('/version')
}
