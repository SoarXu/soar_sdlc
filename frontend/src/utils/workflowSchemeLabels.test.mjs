import { readFileSync } from 'node:fs'
import { strict as assert } from 'node:assert'

function read(path) {
  return readFileSync(path, 'utf8')
}

const projectsView = read('frontend/src/views/ProjectsView.vue')
const workflowView = read('frontend/src/views/WorkflowView.vue')
const projectDetailView = read('frontend/src/views/ProjectDetailView.vue')

assert.match(projectsView, /label="工作流方案"/)
assert.match(projectsView, /v-model="form\.assignee_rule_config_id"/)
assert.match(projectsView, /fetchAssigneeRuleConfigs/)
assert.match(workflowView, /工作流方案列表/)
assert.match(workflowView, /新增工作流方案/)
assert.match(workflowView, /切换到方案/)
assert.doesNotMatch(workflowView, /工作流规则列表|新增工作流规则|转移到规则|选择目标规则/)
assert.match(projectDetailView, /activeTab === 'settings'/)
assert.match(projectDetailView, /label="工作流方案"/)
assert.match(projectDetailView, /v-model="settingsForm\.assignee_rule_config_id"/)
assert.match(projectDetailView, /submitProjectSettings/)
assert.match(projectDetailView, /updateProject/)
assert.match(projectDetailView, /label: '工作流方案', value: 'assignee_rule_config_id'/)

console.log('workflow scheme labels ok')
