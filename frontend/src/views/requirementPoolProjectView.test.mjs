import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const projectDetail = await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')
const requirements = await readFile(new URL('./RequirementsView.vue', import.meta.url), 'utf8')
const requirementDetail = await readFile(new URL('./RequirementDetailView.vue', import.meta.url), 'utf8')

for (const source of [projectDetail, requirements, requirementDetail]) {
  assert.match(source, /requirementIterationOptions/)
  assert.match(source, /requirementIterationLabel/)
  assert.match(source, /fetchIterations\(\{ include_requirement_pool: true \}\)/)
}

assert.match(projectDetail, /requirementPoolForProject\(project\.value, iterations\.value\)/)
assert.match(projectDetail, /iteration_id: projectRequirementPool\.value\?\.id \?\? null/)
assert.match(projectDetail, /const projectIterationOptions = computed\(\(\) => deliveryIterations\(iterations\.value\)/)
assert.match(projectDetail, /bugIterationOptions\(deliveryIterations\(iterations\.value\)/)
assert.match(projectDetail, /<el-tooltip[^>]*content="重命名需求池"/)
assert.match(projectDetail, /:icon="Edit"/)
assert.match(projectDetail, /updateIteration\(projectRequirementPool\.value\.id, \{ name: poolName\.value\.trim\(\) \}\)/)

assert.match(requirements, /watch\(\(\) => form\.project_id, \(projectId\) => \{/)
assert.match(requirements, /if \(editingId\.value\) return/)
assert.match(requirements, /form\.iteration_id = requirementPoolForProject\(selectedProject, iterations\.value\)\?\.id \?\? null/)

for (const source of [projectDetail, requirements, requirementDetail]) {
  assert.doesNotMatch(source, /v-model="(?:requirementForm|form)\.iteration_id" clearable/)
}

console.log('requirement pool project view contracts passed')
