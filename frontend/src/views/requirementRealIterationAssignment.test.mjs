import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { requirementIterationOptions } from '../utils/requirementIterations.js'


function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}


const projects = [{ id: 1 }, { id: 2, parent_id: 1 }]
const iterations = [
  { id: 10, project_ids: [1], state_category: 'start' },
  { id: 11, project_ids: [2], state_category: 'normal' },
  { id: 12, project_ids: [2], state_category: 'terminal' },
  { id: 13, project_ids: [2], state_category: 'in_progress' },
  { id: 14, project_ids: [99], state_category: 'start' }
]

assert.deepEqual(
  requirementIterationOptions(projects[1], projects, iterations).map((item) => item.id),
  [10, 11, 13]
)

const requirementList = source('./RequirementsView.vue')
const projectDetail = source('./ProjectDetailView.vue')
const requirementDetail = source('./RequirementDetailView.vue')
const editDialog = source('../components/work-items/RequirementEditDialog.vue')

for (const formSource of [requirementList, projectDetail, requirementDetail, editDialog]) {
  assert.doesNotMatch(formSource, /requirementPoolForProject/)
  assert.doesNotMatch(formSource, /include_requirement_pool/)
  assert.match(formSource, /!.*iteration_id/)
}

assert.match(requirementList, /el-form-item[^>]+label="迭代"[^>]+required/)
assert.match(projectDetail, /el-form-item[^>]+label="迭代"[^>]+required/)
assert.match(requirementDetail, /el-form-item[^>]+label="迭代"[^>]+required/)
assert.match(editDialog, /el-form-item[^>]+label="迭代"[^>]+required/)

assert.match(projectDetail, /data\.planning_pool/)
assert.match(projectDetail, /planningPoolIterationIds/)
assert.doesNotMatch(projectDetail, /projectRequirementPoolRow/)
assert.doesNotMatch(projectDetail, /editingRequirementPool/)
assert.doesNotMatch(projectDetail, /is_requirement_pool/)
