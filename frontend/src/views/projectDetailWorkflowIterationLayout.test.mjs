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
assert.doesNotMatch(iterationsTemplate, /<el-table-column prop="id" label="ID"/)
assert.doesNotMatch(iterationsTemplate, /is_requirement_pool/)
assert.match(iterationsTemplate, /<router-link class="table-link"/)
assert.match(iterationsTemplate, /:data="pagedProjectIterations"/)
assert.match(iterationsTemplate, /<el-table-column label="操作" :width="projectIterationOperationWidth" fixed="right">/)
assert.match(source, /const projectIterationOperationWidth = computed\(\(\) => workflowActionColumnWidth\(/)
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
assert.match(
  requirementsTemplate,
  /@command="handleRequirementWorkflowCommand\(row, \$event\)"/,
  'the workflow edit command must open the project-detail requirement editor'
)
assert.match(
  source,
  /function handleRequirementWorkflowCommand\(row, \{ commandType \}\) \{\s*if \(commandType === 'edit'\) openRequirementEdit\(row\)/,
  'the project detail must route workflow edit commands to the existing requirement edit dialog'
)

const tasksStart = source.indexOf('<template v-else-if="activeTab === \'tasks\'">')
const tasksEnd = source.indexOf('<template v-else-if="activeTab === \'tests\'">', tasksStart)
assert.notEqual(tasksStart, -1)
assert.notEqual(tasksEnd, -1)
const tasksTemplate = source.slice(tasksStart, tasksEnd)
assert.doesNotMatch(
  tasksTemplate,
  /<el-button v-if="canEditWorkItem\(row\)" link type="primary" @click="openTaskEdit\(row\)">编辑<\/el-button>/,
  'task edit visibility must come from workflow configuration only'
)
assert.match(tasksTemplate, /<WorkflowActionButtons/)
assert.match(tasksTemplate, /@command="handleTaskWorkflowCommand\(row, \$event\)"/)
assert.match(tasksTemplate, /@confirm="removeTask\(row\.id\)"/)
assert.match(
  source,
  /function handleTaskWorkflowCommand\(row, \{ commandType \}\) \{\s*if \(commandType === 'edit'\) openTaskEdit\(row\)/,
  'the project detail must route workflow edit commands to the existing task edit dialog'
)

const bugsStart = source.indexOf('<template v-else-if="activeTab === \'bugs\'">')
const bugsEnd = source.indexOf('<template v-else-if="activeTab === \'members\'">', bugsStart)
assert.notEqual(bugsStart, -1)
assert.notEqual(bugsEnd, -1)
const bugsTemplate = source.slice(bugsStart, bugsEnd)
assert.doesNotMatch(
  bugsTemplate,
  /<el-button v-if="canEditWorkItem\(row\)" link type="primary" @click="openBugEdit\(row\)">编辑<\/el-button>/,
  'bug edit visibility must come from workflow configuration only'
)
assert.match(bugsTemplate, /<WorkflowActionButtons/)
assert.match(bugsTemplate, /@command="handleBugWorkflowCommand\(row, \$event\)"/)
assert.match(
  source,
  /function handleBugWorkflowCommand\(row, \{ commandType \}\) \{\s*if \(commandType === 'edit'\) openBugEdit\(row\)/,
  'the project detail must route workflow edit commands to the existing Bug edit dialog'
)

console.log('project detail workflow and iteration layout contract passed')
