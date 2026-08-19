import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const rolesView = await readFile(new URL('./RolesView.vue', import.meta.url), 'utf8')
const usersApi = await readFile(new URL('../api/users.js', import.meta.url), 'utf8')

assert.match(rolesView, /用户管理/)
assert.match(rolesView, /系统管理员/)
assert.match(rolesView, /<el-tab-pane label="角色" name="roles">/)
assert.match(rolesView, /fetchRoles/)
assert.doesNotMatch(rolesView, /role_ids/)
assert.match(usersApi, /setUserSystemAdmin/)
assert.doesNotMatch(usersApi, /assignUserRoles/)

console.log('user system administrator scope tests passed')
