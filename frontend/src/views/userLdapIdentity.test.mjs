import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const rolesView = await readFile(new URL('./RolesView.vue', import.meta.url), 'utf8')
const usersApi = await readFile(new URL('../api/users.js', import.meta.url), 'utf8')

assert.match(rolesView, /prop="employee_no" label="工号"/)
assert.match(rolesView, /认证来源/)
assert.match(rolesView, /row\.auth_source === 'ldap'/)
assert.match(rolesView, /AD 用户/)
assert.doesNotMatch(rolesView, /AD 域/)
assert.match(rolesView, /openEditUser/)
assert.match(rolesView, /userForm\.employee_no/)
assert.match(rolesView, /v-model="userForm\.employee_no" maxlength="64"/)
assert.match(rolesView, /updateUser/)
assert.match(usersApi, /export function updateUser/)
assert.match(usersApi, /http\.patch\(`\/users\/\$\{userId\}`/)

console.log('user LDAP identity management tests passed')
