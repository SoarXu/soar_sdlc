import assert from 'node:assert/strict'
import { reactive } from 'vue'

import {
  ADVANCED_SECTION_KEYS,
  advancedSectionStates,
  applyAdvancedConfigDraft,
  clearAdvancedSection,
  configuredAdvancedSectionCount,
  createAdvancedConfigDraft,
  isAdvancedConfigDirty,
  moveAdvancedFormField,
  validateAdvancedConfig
} from './workflowAdvancedConfig.js'
import { normalizeWorkflowTransition } from './workflowTransitionConfig.js'

const ADVANCED_OWNED_KEYS = [
  'allowed_role_list',
  'handler_rule',
  'handler_target_roles',
  'handler_fallback_roles',
  'condition_config',
  'condition_routes',
  'form_config',
  'validator_config',
  'ui_config',
  'trigger_config',
  'post_action_config'
]

function createNormalizedTransition() {
  return normalizeWorkflowTransition({
    id: 21,
    definition_id: 8,
    action_key: 'verify_failed',
    action_name: 'Verification failed',
    from_state_id: 10,
    to_state_id: 20,
    allowed_roles: 'tester,project_owner',
    handler_rule: {
      target_type: 'previous_handler',
      target_roles: 'developer,tester',
      fallback_type: 'project_role',
      fallback_roles: 'project_owner'
    },
    condition_config: {
      field: 'review_result',
      routes: { failed: 20 },
      routing_mode: 'automatic'
    },
    form_config: {
      title: 'Verification result',
      fields: [{
        field: 'review_result',
        label: 'Review result',
        type: 'select',
        options: [
          { label: 'Failed', value: 'failed' },
          { label: 'Passed', value: 'passed' }
        ]
      }]
    },
    validator_config: { type: 'requirement_terminal_gate', options: { strict: true } },
    ui_config: { button_type: 'warning', list_display: 'primary', labels: { compact: 'Reject' } },
    trigger_config: { type: 'notification', receiver: 'actor', title: 'Review started' },
    post_action_config: {
      type: 'notification',
      receiver: 'next_handler',
      title: 'Please process again'
    }
  })
}

const reactiveTransition = reactive(createNormalizedTransition())
assert.doesNotThrow(() => createAdvancedConfigDraft(reactiveTransition))
const reactiveDraft = createAdvancedConfigDraft(reactiveTransition)
reactiveDraft.form_config.fields[0].label = 'Reactive draft label'
assert.notEqual(reactiveTransition.form_config.fields[0].label, reactiveDraft.form_config.fields[0].label)

function createEmptyDraft() {
  return createAdvancedConfigDraft(normalizeWorkflowTransition({}))
}

const states = [
  { id: 10 },
  { id: 20 },
  { id: 30 }
]

const SECTION_OWNED_KEYS = {
  rules: ['condition_config', 'condition_routes', 'validator_config'],
  assignment: ['allowed_role_list', 'handler_rule', 'handler_target_roles', 'handler_fallback_roles'],
  form: ['form_config'],
  button: ['ui_config'],
  notification: ['trigger_config', 'post_action_config']
}

assert.deepEqual(ADVANCED_SECTION_KEYS, ['rules', 'assignment', 'form', 'button', 'notification'])

{
  const draft = createAdvancedConfigDraft(createNormalizedTransition())
  draft.form_config.fields.push({ field: 'comment', label: 'Comment', type: 'textarea' })

  assert.equal(moveAdvancedFormField(draft, 1, -1), true)
  assert.deepEqual(draft.form_config.fields.map((field) => field.field), ['comment', 'review_result'])
  assert.equal(moveAdvancedFormField(draft, 0, -1), false)
  assert.equal(moveAdvancedFormField(draft, 1, 1), false)
}

{
  const source = createNormalizedTransition()
  const original = structuredClone(source)
  const draft = createAdvancedConfigDraft(source)

  assert.deepEqual(Object.keys(draft), ADVANCED_OWNED_KEYS)
  for (const key of ADVANCED_OWNED_KEYS) {
    assert.deepEqual(draft[key], source[key])
    assert.notStrictEqual(draft[key], source[key])
  }
  assert.notStrictEqual(draft.form_config.fields, source.form_config.fields)
  assert.notStrictEqual(draft.form_config.fields[0].options, source.form_config.fields[0].options)

  draft.allowed_role_list.push('system_admin')
  draft.handler_rule.target_type = 'project_role'
  draft.handler_target_roles.push('project_owner')
  draft.handler_fallback_roles[0] = 'system_admin'
  draft.condition_config.routes.failed = 30
  draft.condition_routes[0].state_id = 30
  draft.form_config.fields[0].options[0].label = 'Rejected'
  draft.validator_config.options.strict = false
  draft.ui_config.labels.compact = 'Return'
  draft.trigger_config.title = 'Changed trigger'
  draft.post_action_config.title = 'Changed follow-up'

  assert.deepEqual(source, original)
}

{
  const source = createNormalizedTransition()
  const freshDraft = createAdvancedConfigDraft(source)

  assert.equal(isAdvancedConfigDirty(source, freshDraft), false)
  freshDraft.form_config.fields[0].options[0].value = 'rejected'
  assert.equal(isAdvancedConfigDirty(source, freshDraft), true)
}

{
  const source = createNormalizedTransition()
  const draft = createAdvancedConfigDraft(source)
  const originalActionName = source.action_name
  const originalAllowedRoles = source.allowed_roles

  draft.allowed_role_list.push('system_admin')
  draft.form_config.fields[0].label = 'Updated review result'
  draft.action_name = 'Draft metadata must not be applied'
  draft.allowed_roles = 'system_admin'

  const result = applyAdvancedConfigDraft(source, draft)

  assert.strictEqual(result, source)
  assert.equal(source.action_name, originalActionName)
  assert.equal(source.allowed_roles, originalAllowedRoles)
  for (const key of ADVANCED_OWNED_KEYS) {
    assert.deepEqual(source[key], draft[key])
    assert.notStrictEqual(source[key], draft[key])
  }

  const applied = structuredClone(source)
  draft.allowed_role_list.push('project_manager')
  draft.form_config.fields[0].options[0].label = 'Mutated after apply'
  draft.validator_config.options.strict = false
  assert.deepEqual(source, applied)
  assert.equal(isAdvancedConfigDirty(source, createAdvancedConfigDraft(source)), false)
}

{
  assert.deepEqual(advancedSectionStates(createEmptyDraft(), states), {
    rules: 'unconfigured',
    assignment: 'unconfigured',
    form: 'unconfigured',
    button: 'unconfigured',
    notification: 'unconfigured'
  })
}

{
  const draft = createAdvancedConfigDraft(createNormalizedTransition())
  draft.form_config.fields.push({
    field: 'review_result',
    label: 'Duplicate review result',
    type: 'text',
    required: false
  })
  draft.post_action_config.title = '   '

  const result = validateAdvancedConfig(draft, states)

  assert.equal(result.valid, false)
  assert.equal(result.firstSection, 'form')
  assert.deepEqual(Object.keys(result.errors), ADVANCED_SECTION_KEYS)
  assert.ok(result.errors.form.some((item) => item.code === 'duplicate_field_key'))
  assert.ok(result.errors.notification.some((item) => item.code === 'notification_title_required'))
  assert.ok(result.errors.form.some((item) => (
    item.code === 'duplicate_field_key' && item.message === '字段键不能重复'
  )))
  assert.ok(result.errors.notification.some((item) => (
    item.code === 'notification_title_required' && item.message === '通知标题不能为空'
  )))
  for (const section of ADVANCED_SECTION_KEYS) {
    for (const error of result.errors[section]) {
      assert.deepEqual(Object.keys(error), ['code', 'field', 'message'])
      assert.equal(typeof error.code, 'string')
      assert.equal(typeof error.field, 'string')
      assert.equal(typeof error.message, 'string')
    }
  }
}

{
  const expectedResets = {
    rules: {
      condition_config: {},
      condition_routes: [],
      validator_config: null
    },
    assignment: {
      allowed_role_list: [],
      handler_rule: {
        target_type: 'keep_current',
        target_roles: '',
        fallback_type: 'keep_current',
        fallback_roles: ''
      },
      handler_target_roles: [],
      handler_fallback_roles: []
    },
    form: { form_config: { fields: [] } },
    button: { ui_config: {} },
    notification: { trigger_config: null, post_action_config: null }
  }

  for (const section of ADVANCED_SECTION_KEYS) {
    const source = createAdvancedConfigDraft(createNormalizedTransition())
    const original = structuredClone(source)
    const cleared = clearAdvancedSection(source, section)

    assert.notStrictEqual(cleared, source)
    assert.deepEqual(source, original)
    for (const [key, value] of Object.entries(expectedResets[section])) {
      assert.deepEqual(cleared[key], value)
    }
    for (const otherSection of ADVANCED_SECTION_KEYS.filter((key) => key !== section)) {
      for (const key of SECTION_OWNED_KEYS[otherSection]) {
        assert.deepEqual(cleared[key], original[key])
        if (cleared[key] && typeof cleared[key] === 'object') {
          assert.notStrictEqual(cleared[key], source[key])
        }
      }
    }
  }
}

{
  const draft = createEmptyDraft()
  draft.form_config.fields = [
    { field: ' ', type: 'text' },
    { field: 'category', type: 'text' },
    { field: 'category', type: 'text' }
  ]

  const result = validateAdvancedConfig(draft, states)

  assert.ok(result.errors.form.some((item) => item.code === 'field_key_required'))
  assert.ok(result.errors.form.some((item) => item.code === 'duplicate_field_key'))
}

{
  const draft = createEmptyDraft()
  draft.form_config.fields = [{ field: 'category', type: 'select', option_lines: '  ', options: [] }]
  assert.ok(validateAdvancedConfig(draft, states).errors.form.some((item) => item.code === 'select_options_required'))

  for (const incompleteOptions of [
    { option_lines: 'Only label:' },
    { option_lines: ':only_value' },
    { options: [{ label: '', value: 'only_value' }] },
    { options: [{ label: 'Only label', value: '' }] }
  ]) {
    const incompleteDraft = createEmptyDraft()
    incompleteDraft.form_config.fields = [{ field: 'category', type: 'select', ...incompleteOptions }]
    assert.ok(validateAdvancedConfig(incompleteDraft, states).errors.form.some(
      (item) => item.code === 'select_options_required'
    ))
  }

  for (const field of [
    { field: 'category', type: 'select', dictionary: 'bug_type' },
    { field: 'category', type: 'select', option_lines: 'A:a' },
    { field: 'category', type: 'select', options: [{ label: 'A', value: 'a' }] }
  ]) {
    const validDraft = createEmptyDraft()
    validDraft.form_config.fields = [field]
    assert.equal(validateAdvancedConfig(validDraft, states).valid, true)
  }
}

{
  const draft = createEmptyDraft()
  draft.condition_routes = [{ value: ' ', state_id: 999 }]

  const result = validateAdvancedConfig(draft, states)
  const codes = result.errors.rules.map((item) => item.code)

  assert.ok(codes.includes('route_field_required'))
  assert.ok(codes.includes('route_value_required'))
  assert.ok(codes.includes('route_status_invalid'))
}

{
  const draft = createEmptyDraft()
  draft.condition_config = { field: 'category', route_dictionary: 'bug_type' }
  draft.condition_routes = [{ value: 'defect', state_id: 30 }]

  assert.ok(validateAdvancedConfig(draft, states).errors.rules.some(
    (item) => item.code === 'dictionary_static_routes_conflict'
  ))
}

{
  const draft = createEmptyDraft()
  draft.condition_config = { field: 'category' }

  assert.ok(validateAdvancedConfig(draft, states).errors.rules.some((item) => item.code === 'route_field_missing'))

  const dictionaryDraft = createEmptyDraft()
  dictionaryDraft.condition_config = { field: 'bug_type', route_dictionary: 'bug_type' }
  assert.equal(validateAdvancedConfig(dictionaryDraft, states).valid, true)
}

{
  const draft = createEmptyDraft()
  draft.condition_config = { routing_mode: 'automatic_with_override', allow_override_roles: [] }

  assert.ok(validateAdvancedConfig(draft, states).errors.rules.some((item) => item.code === 'override_roles_required'))
  draft.condition_config.allow_override_roles = ['project_owner']
  assert.equal(validateAdvancedConfig(draft, states).valid, true)
}

{
  const draft = createEmptyDraft()
  draft.handler_rule.target_type = 'project_role'
  draft.handler_rule.fallback_type = 'project_role'

  const result = validateAdvancedConfig(draft, states)
  assert.ok(result.errors.assignment.some((item) => item.code === 'target_roles_required'))
  assert.ok(result.errors.assignment.some((item) => item.code === 'fallback_roles_required'))

  draft.handler_target_roles = ['developer']
  draft.handler_fallback_roles = ['project_owner']
  assert.equal(validateAdvancedConfig(draft, states).valid, true)
}

{
  const draft = createEmptyDraft()
  draft.trigger_config = { type: 'notification', receiver: '', title: 'Before transition' }
  draft.post_action_config = { type: 'notification', receiver: 'next_handler', title: '' }

  const result = validateAdvancedConfig(draft, states)
  assert.ok(result.errors.notification.some((item) => (
    item.code === 'notification_receiver_required' && item.field === 'trigger_config.receiver'
  )))
  assert.ok(result.errors.notification.some((item) => (
    item.code === 'notification_title_required' && item.field === 'post_action_config.title'
  )))
}

{
  const configuredCases = [
    ['rules', (draft) => { draft.validator_config = { type: 'bug_close_gate' } }],
    ['assignment', (draft) => { draft.handler_rule.allow_manual_owner = true }],
    ['form', (draft) => { draft.form_config.submit_text = 'Submit' }],
    ['button', (draft) => { draft.ui_config.button_type = 'primary' }],
    ['notification', (draft) => {
      draft.trigger_config = { type: 'notification', receiver: 'actor', title: 'Started' }
    }]
  ]

  for (const [section, configure] of configuredCases) {
    const draft = createEmptyDraft()
    configure(draft)
    assert.equal(advancedSectionStates(draft, states)[section], 'configured')
  }

  const draft = createEmptyDraft()
  draft.form_config.fields = [{ field: '', type: 'text' }]
  draft.ui_config.button_type = 'primary'
  const sectionStates = advancedSectionStates(draft, states)

  assert.equal(sectionStates.form, 'invalid')
  assert.equal(sectionStates.button, 'configured')
  assert.equal(Object.values(sectionStates).filter((value) => value === 'invalid').length, 1)
  assert.equal(configuredAdvancedSectionCount(draft, states), 2)
}

console.log('workflow advanced config tests passed')
