import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')

assert.match(source, /import \{ fetchRoles \} from '\.\.\/api\/roles'/)
assert.match(source, /fetchRoles\(\)/)
assert.match(source, /role\.role_key !== 'system_admin'/)
assert.match(source, /projectMemberRoleOptions/)

console.log('project members use the business role catalog')
