import { http } from './http'

export function fetchLdapConfig() { return http.get('/admin/ldap') }
export function saveLdapConfig(payload) { return http.put('/admin/ldap', payload) }
export function testLdapConnection() { return http.post('/admin/ldap/test') }
export function fetchLdapDirectoryUsers(params) { return http.get('/admin/ldap/directory-users', { params }) }
export function syncLdapUsers(items) { return http.post('/admin/ldap/sync', { items }, { timeout: 900000 }) }
export function syncBoundLdapUsers() { return http.post('/admin/ldap/sync-bound-users', null, { timeout: 900000 }) }
export function fetchLdapSyncRuns(params) { return http.get('/admin/ldap/sync-runs', { params }) }
