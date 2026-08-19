import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProjectComponentsView.vue', import.meta.url), 'utf8')

assert.match(source, /fetchBusinessComponents/)
assert.match(source, /fetchUsers/)
assert.match(source, /memberLabel\(row\.members\)/)
assert.match(source, /function memberLabel\(members\)/)
assert.match(source, /saveBusinessComponentMembers/)
assert.match(source, /updateBusinessComponent/)
assert.match(source, /fetchAssigneeRuleConfigs/)
assert.match(source, /projectRoleOptions/)
assert.match(source, /projectRoleLabel/)
assert.doesNotMatch(source, /const componentMemberRoles =/)
assert.match(source, /workflowSchemeLabel\(row\.workflow_scheme_id\)/)
assert.match(source, /编辑/)
assert.match(source, />创建组件<\/el-button>/)
assert.match(source, /title="创建组件"/)
assert.doesNotMatch(source, /从已关闭项目创建组件/)
assert.match(source, /请选择该成员在当前项目中的角色/)
assert.match(source, /projectRoleOptions\(member\.user_id\)/)

console.log('project components member display contract passed')
