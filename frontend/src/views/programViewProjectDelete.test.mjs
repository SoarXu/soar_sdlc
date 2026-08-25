import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProgramsView.vue', import.meta.url), 'utf8')

assert.match(source, /deleteProject,/)
assert.match(source, /fetchProjectMembersBatch,/)
assert.match(source, /const projectMembersById = ref\(\{\}\)/)
assert.match(source, /const currentUser = computed\(\(\) => currentUserFromStorage\(users\.value\)\)/)
assert.match(source, /<el-button v-if="canManageProjectRow\(row\)" link type="danger" @click="confirmRemoveProject\(row\.id\)">删除<\/el-button>/)
assert.match(source, /loadProjectMembers\(\)/)
assert.match(source, /function canManageProjectRow\(row\)/)
assert.match(source, /await ElMessageBox\.confirm\('确认删除该项目？子项目将一并删除。', '提示', \{ type: 'warning' \}\)/)
assert.match(source, /await removeProject\(id\)/)

console.log('program view project delete tests passed')
