import assert from 'node:assert/strict'

import {
  normalizeWorkflowTransition,
  serializeWorkflowTransition,
  unsupportedWorkflowConfigSections
} from './workflowTransitionConfig.js'

const source = {
  id: 9,
  definition_id: 3,
  action_key: 'classify',
  action_name: 'Classify',
  from_state_id: 11,
  to_state_id: 12,
  allowed_roles: 'current_handler,system_admin',
  handler_rule: {
    target_type: 'project_role',
    target_roles: 'developer,tester',
    fallback_type: 'project_owner',
    fallback_roles: ''
  },
  condition_config: { field: 'bug_type', routes: { code_issue: 12 }, routing_mode: 'automatic' },
  form_config: { fields: [
    { field: 'bug_type', label: 'Bug Type', type: 'select', dictionary: 'bug_type' },
    { field: 'resolution', label: 'Resolution', type: 'select', options: [{ label: 'Fixed', value: 'fixed' }] }
  ] },
  validator_config: { type: 'bug_close_gate' },
  ui_config: { button_type: 'warning', list_display: 'primary', action_category: 'management' },
  diagram_config: {
    version: 1,
    routing_mode: 'manual',
    source_anchor: { side: 'bottom', ratio: 0.5 },
    target_anchor: { side: 'top', ratio: 0.5 },
    waypoints: [{ x: 120, y: 180 }, { x: 320, y: 180 }]
  },
  trigger_config: { type: 'notification', receiver: 'actor', title: 'Started' },
  post_action_config: { type: 'notification', receiver: 'next_handler', title: 'Assigned' }
}

const normalized = normalizeWorkflowTransition(source)
assert.deepEqual(normalized.allowed_role_list, ['current_handler', 'system_admin'])
assert.deepEqual(normalized.handler_target_roles, ['developer', 'tester'])
assert.deepEqual(normalized.condition_routes, [{ value: 'code_issue', state_id: 12 }])

const serialized = serializeWorkflowTransition(normalized)
assert.equal(serialized.id, 9)
assert.equal(serialized.action_key, 'classify')
assert.equal('definition_id' in serialized, false)
for (const key of ['condition_config', 'form_config', 'validator_config', 'ui_config', 'diagram_config', 'trigger_config', 'post_action_config']) {
  assert.deepEqual(serialized[key], source[key])
}
normalized.diagram_config.waypoints[0].x = 999
assert.equal(source.diagram_config.waypoints[0].x, 120)

assert.deepEqual(unsupportedWorkflowConfigSections(source), [])
const historical = { ...source, trigger_config: { type: 'legacy_script', source: 'keep me' } }
assert.deepEqual(unsupportedWorkflowConfigSections(historical), ['trigger_config'])
assert.deepEqual(serializeWorkflowTransition(normalizeWorkflowTransition(historical)).trigger_config, historical.trigger_config)

const dictionarySource = {
  ...source,
  condition_config: { field: 'bug_type', route_dictionary: 'bug_type', routing_mode: 'automatic' }
}
const dictionaryNormalized = normalizeWorkflowTransition(dictionarySource)
assert.deepEqual(dictionaryNormalized.condition_routes, [])
const dictionaryRoundTrip = serializeWorkflowTransition(dictionaryNormalized)
assert.equal(dictionaryRoundTrip.condition_config.route_dictionary, 'bug_type')
assert.equal('routes' in dictionaryRoundTrip.condition_config, false)

console.log('workflow transition config tests passed')
