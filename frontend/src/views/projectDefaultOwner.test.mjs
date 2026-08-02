import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const programsView = await readFile(new URL('./ProgramsView.vue', import.meta.url), 'utf8')
const projectsView = await readFile(new URL('./ProjectsView.vue', import.meta.url), 'utf8')

function functionBlock(source, name, nextName) {
  const start = source.indexOf(`function ${name}`)
  const end = source.indexOf(nextName, start)
  assert.notEqual(start, -1, `missing ${name}`)
  assert.notEqual(end, -1, `missing boundary after ${name}`)
  return source.slice(start, end)
}

const resetProjectForm = functionBlock(programsView, 'resetProjectForm', 'function openProjectCreate')
const resetForm = functionBlock(projectsView, 'resetForm', 'function buildProjectTree')

for (const formReset of [resetProjectForm, resetForm]) {
  assert.match(formReset, /localStorage\.getItem\('current_user_id'\)/,
    'new project forms must read the authenticated user ID')
  assert.match(formReset, /users\.value\.some\(\(user\) => user\.id === currentUserId\)/,
    'new project forms must only preselect a current user returned by the user list')
  assert.match(formReset, /owner_id:\s*users\.value\.some\(\(user\) => user\.id === currentUserId\) \? currentUserId : null/,
    'new project forms must preselect the authenticated user as owner')
}

assert.match(projectsView, /const canCreateProject = computed\(\(\) => Boolean\(currentUser\.value\)\)/,
  'any authenticated user must see the project creation action')
assert.match(projectsView, /<el-button v-if="canManageProjectRow\(row\)" link type="danger" @click="confirmRemoveProject\(row\.id\)">删除<\/el-button>/,
  'project deletion must use the unified project governance permission')
assert.match(projectsView, /function canManageProjectRow\(row\) \{[\s\S]*?isProgramOwnerAncestor\(row\.program_id\)/,
  'project-set owners must manage projects in their project-set hierarchy')

console.log('project default owner UI contract passed')
