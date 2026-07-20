import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  buildWorkflowSchemeCreatePayload,
  groupWorkflowTemplateSources,
  lifecycleStatusMeta,
  templateSourceValue
} from './workflowSchemeCreation.js'

{
  const payload = buildWorkflowSchemeCreatePayload({
    name: '空白研发流程',
    description: '从零配置',
    creation_mode: 'blank',
    template_source_value: ''
  })

  assert.deepEqual(payload, {
    name: '空白研发流程',
    description: '从零配置',
    creation_mode: 'blank'
  })
}

{
  const payload = buildWorkflowSchemeCreatePayload({
    name: '标准流程副本',
    description: '',
    creation_mode: 'template',
    template_source_value: 'system:system-standard'
  })

  assert.deepEqual(payload, {
    name: '标准流程副本',
    description: null,
    creation_mode: 'template',
    template_source: { source_type: 'system', source_id: 'system-standard' }
  })
}

{
  const sources = [
    { source_type: 'scheme', source_id: '12', name: '团队流程', lifecycle_status: 'draft' },
    { source_type: 'system', source_id: 'system-standard', name: '系统标准方案', lifecycle_status: 'enabled' }
  ]
  const groups = groupWorkflowTemplateSources(sources)

  assert.deepEqual(groups.map((group) => group.label), ['系统模板', '已有方案'])
  assert.equal(groups[0].options[0].value, 'system:system-standard')
  assert.equal(groups[1].options[0].value, 'scheme:12')
  assert.equal(templateSourceValue(sources[0]), 'scheme:12')
}

assert.deepEqual(lifecycleStatusMeta('draft'), { label: '草稿', type: 'warning' })
assert.deepEqual(lifecycleStatusMeta('enabled'), { label: '已启用', type: 'success' })
assert.deepEqual(lifecycleStatusMeta('disabled'), { label: '已停用', type: 'info' })

const workflowView = readFileSync('frontend/src/views/WorkflowView.vue', 'utf8')
const projectDetailView = readFileSync('frontend/src/views/ProjectDetailView.vue', 'utf8')
const projectsView = readFileSync('frontend/src/views/ProjectsView.vue', 'utf8')

assert.match(workflowView, /creation_mode/)
assert.match(workflowView, /template_source_value/)
assert.match(workflowView, /source\.description/)
assert.match(workflowView, /enableAssigneeRuleConfig/)
assert.match(workflowView, /disableAssigneeRuleConfig/)
assert.doesNotMatch(workflowView, /form\.enabled|deleteAssigneeRuleConfig/)
assert.match(workflowView, /:role-options="workflowExecutionRoleOptions"/)
for (const [label, value] of [
  ['创建人', 'creator'],
  ['项目负责人', 'project_owner'],
  ['当前处理人', 'current_handler'],
  ['系统管理员', 'system_admin']
]) {
  assert.match(
    workflowView,
    new RegExp(`\\{ label: '${label}', value: '${value}' \\}`),
    `workflow role ${value} must have a Chinese label`
  )
}
assert.match(projectDetailView, /lifecycle_status === 'enabled'/)
assert.match(projectsView, /lifecycle_status === 'enabled'/)

console.log('workflow scheme creation and lifecycle tests passed')
