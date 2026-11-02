import { http } from './http'

export function fetchLdapProposers(query) {
  return http.get('/directory/proposers', { params: query ? { q: query } : undefined })
}
