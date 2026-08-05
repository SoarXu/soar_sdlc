import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const [projectDetail, iterationDetail] = await Promise.all([
  readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8'),
  readFile(new URL('./IterationDetailView.vue', import.meta.url), 'utf8')
])

assert.match(
  projectDetail,
  /function canManageIterationDelivery\(row\) \{[\s\S]*?row\.owner_id === currentUser\.value\?\.id/,
  'an assigned iteration owner must see delivery actions in the project iteration table'
)
assert.match(
  projectDetail,
  /WorkflowActionButtons v-if="canManageIterationDelivery\(row\) && !row\.is_requirement_pool"/,
  'iteration lifecycle actions must use the delivery permission rather than project governance only'
)
assert.match(
  projectDetail,
  /el-popconfirm v-if="canManageCurrentProject && !row\.is_requirement_pool"/,
  'iteration deletion must remain a project governance action'
)
assert.match(
  iterationDetail,
  /const isIterationOwner = computed\(\(\) => iteration\.value\.owner_id === currentUser\.value\?\.id\)/,
  'iteration detail must recognize the assigned owner independently from project governance'
)
assert.match(
  iterationDetail,
  /const canManageIteration = computed\(\(\) => isIterationOwner\.value \|\|/,
  'iteration owners must be able to manage delivery scope and lifecycle from detail'
)

console.log('iteration owner permission source contract passed')
