import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const viewPath = fileURLToPath(new URL('./ProjectDetailView.vue', import.meta.url))
const source = (await readFile(viewPath, 'utf8')).replace(/\r\n/g, '\n')

const settingsSelectorStart = source.indexOf('<el-select\n                  v-model="settingsForm.assignee_rule_config_id"')
const settingsSelectorEnd = source.indexOf('>', settingsSelectorStart)
assert.notEqual(settingsSelectorStart, -1)
assert.notEqual(settingsSelectorEnd, -1)
assert.doesNotMatch(source.slice(settingsSelectorStart, settingsSelectorEnd + 1), /\bclearable\b/)

const iterationsStart = source.indexOf('<template v-else-if="activeTab === \'iterations\'">')
const iterationsEnd = source.indexOf('<template v-else-if="activeTab === \'requirements\'">', iterationsStart)
assert.notEqual(iterationsStart, -1)
assert.notEqual(iterationsEnd, -1)
const iterationsTemplate = source.slice(iterationsStart, iterationsEnd)

assert.equal((iterationsTemplate.match(/<el-table(?:\s|>)/g) || []).length, 1)
assert.match(iterationsTemplate, /v-if="row\.is_requirement_pool"[^>]*>\{\{ requirementIterationLabel\(row\) \}\}/)
assert.match(iterationsTemplate, /:data="pagedProjectIterations"/)
assert.match(
  iterationsTemplate,
  /<template #default="\{ row \}">\s*<div class="table-actions">/,
  'iteration workflow, defer, edit and delete actions must share one layout container'
)

const requirementsStart = source.indexOf('<template v-else-if="activeTab === \'requirements\'">')
const requirementsEnd = source.indexOf('<template v-else-if="activeTab === \'tasks\'">', requirementsStart)
assert.notEqual(requirementsStart, -1)
assert.notEqual(requirementsEnd, -1)
const requirementsTemplate = source.slice(requirementsStart, requirementsEnd)
assert.doesNotMatch(
  requirementsTemplate,
  /<el-button v-if="canEditWorkItem\(row\)" link type="primary" @click="openRequirementEdit\(row\)">/,
  'requirement edit visibility must come from the workflow action configuration only'
)
assert.match(requirementsTemplate, /<WorkflowActionButtons/)

console.log('project detail workflow and iteration layout contract passed')
