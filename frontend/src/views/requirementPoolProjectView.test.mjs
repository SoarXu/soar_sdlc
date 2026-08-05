import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const projectDetail = (await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')).replace(/\r\n/g, '\n')
const requirements = (await readFile(new URL('./RequirementsView.vue', import.meta.url), 'utf8')).replace(/\r\n/g, '\n')
const requirementDetail = (await readFile(new URL('./RequirementDetailView.vue', import.meta.url), 'utf8')).replace(/\r\n/g, '\n')

for (const source of [projectDetail, requirements, requirementDetail]) {
  assert.match(source, /requirementIterationOptions/)
  assert.match(source, /requirementIterationLabel/)
  assert.match(source, /fetchIterations\(\{ include_requirement_pool: true \}\)/)
}

assert.match(projectDetail, /requirementPoolForProject\(project\.value, iterations\.value\)/)
assert.match(projectDetail, /iteration_id: projectRequirementPool\.value\?\.id \?\? null/)
assert.match(projectDetail, /const projectIterationOptions = computed\(\(\) => deliveryIterations\(iterations\.value\)/)
assert.match(projectDetail, /bugIterationOptions\(deliveryIterations\(iterations\.value\)/)
assert.match(projectDetail, /const projectRequirementPoolRow = ref\(null\)/)
assert.match(projectDetail, /projectRequirementPoolRow\.value = data\.requirement_pool \|\| null/)
assert.match(projectDetail, /<el-table :data="pagedProjectIterations"/)
assert.doesNotMatch(projectDetail, /<el-table v-if="projectRequirementPoolRow"/)
assert.match(projectDetail, /requirementIterationLabel\(row\)/)
assert.match(projectDetail, /v-if="canManageCurrentProject \|\| canManageIterationDelivery\(row\)" link type="primary" @click="openIterationEdit\(row\)"/)
assert.doesNotMatch(projectDetail, /<el-tooltip[^>]*content="重命名需求池"/)
assert.doesNotMatch(projectDetail, /requirementPoolRenameVisible|openRequirementPoolRename|renameRequirementPool|poolName/)
assert.match(projectDetail, /const editingRequirementPool = ref\(false\)/)
assert.match(projectDetail, /editingRequirementPool\.value = Boolean\(row\.is_requirement_pool\)/)
assert.match(projectDetail, /:disabled="editingRequirementPool \|\| !editingIterationCanAdminister"/)
assert.match(projectDetail, /const payload = editingRequirementPool\.value\n\s*\? \{ name: iterationForm\.name\.trim\(\) \}/)
assert.match(projectDetail, /<WorkflowActionButtons v-if="canManageIterationDelivery\(row\) && !row\.is_requirement_pool"/)
assert.match(projectDetail, /canManageIterationDelivery\(row\) && !row\.is_requirement_pool && iterationCanDefer\(row\)/)
assert.match(projectDetail, /<el-popconfirm v-if="canManageCurrentProject && !row\.is_requirement_pool"/)

assert.match(requirements, /watch\(\(\) => form\.project_id, \(projectId\) => \{/)
assert.match(requirements, /if \(editingId\.value\) return/)
assert.match(requirements, /form\.iteration_id = requirementPoolForProject\(selectedProject, iterations\.value\)\?\.id \?\? null/)

for (const source of [projectDetail, requirements, requirementDetail]) {
  assert.doesNotMatch(source, /v-model="(?:requirementForm|form)\.iteration_id" clearable/)
}

console.log('requirement pool project view contracts passed')
