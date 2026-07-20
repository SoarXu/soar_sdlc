const VALIDATOR_TYPES = new Set([
  'bug_close_gate',
  'requirement_terminal_gate',
  'iteration_terminal_gate',
  'project_close_gate'
])
const AUTOMATION_TYPES = new Set(['notification'])
const FIELD_TYPES = new Set(['text', 'textarea', 'select', 'number', 'date', 'datetime'])

function roleArray(value) {
  if (Array.isArray(value)) return value
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function normalizeWorkflowTransition(item) {
  const handlerRule = item.handler_rule || {
    target_type: 'keep_current',
    target_roles: '',
    fallback_type: 'keep_current',
    fallback_roles: ''
  }
  return {
    ...item,
    condition_config: { ...(item.condition_config || {}) },
    form_config: {
      ...(item.form_config || {}),
      fields: (item.form_config?.fields || []).map((field) => ({
        ...field,
        option_lines: (field.options || []).map((option) => `${option.label}:${option.value}`).join('\n')
      }))
    },
    ui_config: { ...(item.ui_config || {}) },
    diagram_config: item.diagram_config ? structuredClone(item.diagram_config) : null,
    validator_config: item.validator_config ? { ...item.validator_config } : null,
    trigger_config: item.trigger_config ? { ...item.trigger_config } : null,
    post_action_config: item.post_action_config ? { ...item.post_action_config } : null,
    condition_routes: Object.entries(item.condition_config?.routes || {}).map(([value, stateId]) => ({
      value,
      state_id: Number(stateId)
    })),
    handler_rule: {
      ...handlerRule,
      target_type: handlerRule.target_type || 'keep_current',
      target_roles: roleArray(handlerRule.target_roles).join(','),
      fallback_type: handlerRule.fallback_type || 'keep_current',
      fallback_roles: roleArray(handlerRule.fallback_roles).join(',')
    },
    allowed_role_list: roleArray(item.allowed_roles),
    handler_target_roles: roleArray(handlerRule.target_roles),
    handler_fallback_roles: roleArray(handlerRule.fallback_roles)
  }
}

export function serializeWorkflowTransition(item) {
  const {
    id,
    definition_id,
    action_key,
    _client_id,
    allowed_role_list,
    handler_target_roles,
    handler_fallback_roles,
    condition_routes,
    ...rest
  } = item
  const conditionConfig = { ...(rest.condition_config || {}) }
  const uiConfig = { ...(rest.ui_config || {}) }
  for (const key of ['hidden', 'list_priority', 'visible_in_detail', 'visible_in_list']) delete uiConfig[key]
  uiConfig.list_display = uiConfig.list_display === 'primary' ? 'primary' : 'more'
  const formConfig = { ...(rest.form_config || {}) }
  formConfig.fields = (formConfig.fields || []).map(({ option_lines, ...field }) => ({
    ...field,
    ...(field.type === 'select' && field.dictionary !== 'bug_type'
      ? {
          options: String(option_lines || '')
            .split('\n')
            .map((line) => line.trim())
            .filter(Boolean)
            .map((line) => {
              const separator = line.indexOf(':')
              return separator < 0
                ? { label: line, value: line }
                : { label: line.slice(0, separator).trim(), value: line.slice(separator + 1).trim() }
            })
        }
      : {})
  }))
  if (condition_routes.length || Object.hasOwn(conditionConfig, 'routes')) {
    conditionConfig.routes = Object.fromEntries(
      condition_routes
        .filter((route) => route.value && Number.isInteger(route.state_id))
        .map((route) => [route.value, route.state_id])
    )
  }
  return {
    ...(id ? { id } : {}),
    ...rest,
    condition_config: Object.keys(conditionConfig).length ? conditionConfig : null,
    form_config: formConfig.fields?.length || formConfig.title || formConfig.submit_text
      ? formConfig
      : null,
    ui_config: uiConfig,
    allowed_roles: allowed_role_list.join(','),
    handler_rule: {
      ...rest.handler_rule,
      target_roles: handler_target_roles.join(','),
      fallback_roles: handler_fallback_roles.join(',')
    }
  }
}

export function unsupportedWorkflowConfigSections(item = {}) {
  const unsupported = []
  const validators = Array.isArray(item.validator_config) ? item.validator_config : [item.validator_config]
  if (validators.some((entry) => entry && !VALIDATOR_TYPES.has(entry.type))) unsupported.push('validator_config')
  for (const key of ['trigger_config', 'post_action_config']) {
    const entries = Array.isArray(item[key]) ? item[key] : [item[key]]
    if (entries.some((entry) => entry && !AUTOMATION_TYPES.has(entry.type))) unsupported.push(key)
  }
  const fields = item.form_config?.fields || []
  if (fields.some((field) => !FIELD_TYPES.has(field.type))) unsupported.push('form_config')
  return unsupported
}
