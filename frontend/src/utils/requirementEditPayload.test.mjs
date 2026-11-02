import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { requirementEditPayload } from './requirementEditPayload.js'

const form = {
  id: 7895,
  project_id: 19418,
  iteration_id: 20,
  title: '提交评审',
  requirement_type: '功能',
  priority: '3',
  proposer: '',
  description: '',
  acceptance_criteria: '',
  owner_id: 11,
  workflow_definition_id: 7,
  current_state_id: 9,
  status_name: '待分派',
  linked_tasks: [{ id: 1 }],
  primary_component: null
}

assert.deepEqual(requirementEditPayload(form, 19418), {
  project_id: 19418,
  iteration_id: 20,
  title: '提交评审',
  requirement_type: '功能',
  priority: '3',
  proposer: null,
  description: '',
  acceptance_criteria: ''
})

const projectDetail = readFileSync(new URL('../views/ProjectDetailView.vue', import.meta.url), 'utf8')
assert.match(projectDetail, /updateRequirement\(editingRequirementId\.value, requirementEditPayload\(requirementForm, projectId\.value\)\)/)
