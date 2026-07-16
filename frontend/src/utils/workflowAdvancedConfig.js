import { toRaw } from 'vue'

export const ADVANCED_SECTION_KEYS = ['rules', 'assignment', 'form', 'button', 'notification']

const ADVANCED_KEYS = [
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

function clone(value) {
  return value === undefined ? undefined : structuredClone(toRaw(value))
}

export function createAdvancedConfigDraft(transition) {
  return Object.fromEntries(ADVANCED_KEYS.map((key) => [key, clone(transition[key])]))
}

export function isAdvancedConfigDirty(transition, draft) {
  return JSON.stringify(createAdvancedConfigDraft(transition)) !== JSON.stringify(draft)
}

export function applyAdvancedConfigDraft(transition, draft) {
  for (const key of ADVANCED_KEYS) transition[key] = clone(draft[key])
  return transition
}

export function moveAdvancedFormField(draft, index, offset) {
  const fields = draft.form_config?.fields
  const targetIndex = index + offset
  if (!Array.isArray(fields) || targetIndex < 0 || targetIndex >= fields.length) return false
  const [field] = fields.splice(index, 1)
  fields.splice(targetIndex, 0, field)
  return true
}

export function clearAdvancedSection(source, section) {
  const draft = clone(source)
  if (section === 'rules') {
    draft.condition_config = {}
    draft.condition_routes = []
    draft.validator_config = null
  } else if (section === 'assignment') {
    draft.allowed_role_list = []
    draft.handler_rule = {
      target_type: 'keep_current',
      target_roles: '',
      fallback_type: 'keep_current',
      fallback_roles: ''
    }
    draft.handler_target_roles = []
    draft.handler_fallback_roles = []
  } else if (section === 'form') {
    draft.form_config = { fields: [] }
  } else if (section === 'button') {
    draft.ui_config = {}
  } else if (section === 'notification') {
    draft.trigger_config = null
    draft.post_action_config = null
  }
  return draft
}

export function validateAdvancedConfig(draft, states) {
  const errors = Object.fromEntries(ADVANCED_SECTION_KEYS.map((key) => [key, []]))
  const add = (section, code, field, message) => errors[section].push({ code, field, message })
  const statusKeys = new Set((states || []).map((item) => item.status_key))
  const fields = draft.form_config?.fields || []
  const fieldKeys = fields.map((field) => String(field.field || '').trim())

  fields.forEach((field, index) => {
    const key = fieldKeys[index]
    if (!key) {
      add('form', 'field_key_required', `form_config.fields.${index}.field`, '字段键不能为空')
    }
    if (key && fieldKeys.indexOf(key) !== index) {
      add('form', 'duplicate_field_key', `form_config.fields.${index}.field`, '字段键不能重复')
    }
    const hasOptions = (field.options || []).some((option) => (
      String(option.label || '').trim() && String(option.value || '').trim()
    ))
    const hasOptionLines = String(field.option_lines || '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .some((line) => {
        const separator = line.indexOf(':')
        return separator < 0 || Boolean(line.slice(0, separator).trim() && line.slice(separator + 1).trim())
      })
    if (
      field.type === 'select' &&
      field.dictionary !== 'bug_type' &&
      !hasOptions &&
      !hasOptionLines
    ) {
      add('form', 'select_options_required', `form_config.fields.${index}.options`, '下拉字段必须配置完整选项')
    }
  })

  const condition = draft.condition_config || {}
  const routes = draft.condition_routes || []
  const routeField = String(condition.field || '').trim()
  if (condition.route_dictionary && routes.length) {
    add(
      'rules',
      'dictionary_static_routes_conflict',
      'condition_config.route_dictionary',
      '字典路由不能同时配置静态路由'
    )
  }
  if (routes.length && !routeField) {
    add('rules', 'route_field_required', 'condition_config.field', '请选择路由字段')
  }
  if (routeField && condition.route_dictionary !== 'bug_type' && !fieldKeys.includes(routeField)) {
    add('rules', 'route_field_missing', 'condition_config.field', '路由字段必须存在于动作表单')
  }
  routes.forEach((route, index) => {
    if (!String(route.value || '').trim()) {
      add('rules', 'route_value_required', `condition_routes.${index}.value`, '路由值不能为空')
    }
    if (!statusKeys.has(route.status)) {
      add('rules', 'route_status_invalid', `condition_routes.${index}.status`, '目标状态无效')
    }
  })
  if (condition.routing_mode === 'automatic_with_override' && !(condition.allow_override_roles || []).length) {
    add(
      'rules',
      'override_roles_required',
      'condition_config.allow_override_roles',
      '至少选择一个允许覆盖角色'
    )
  }

  if (draft.handler_rule?.target_type === 'project_role' && !(draft.handler_target_roles || []).length) {
    add('assignment', 'target_roles_required', 'handler_target_roles', '请选择主要目标角色')
  }
  if (draft.handler_rule?.fallback_type === 'project_role' && !(draft.handler_fallback_roles || []).length) {
    add('assignment', 'fallback_roles_required', 'handler_fallback_roles', '请选择回退目标角色')
  }

  for (const [field, config] of [
    ['trigger_config', draft.trigger_config],
    ['post_action_config', draft.post_action_config]
  ]) {
    if (!config) continue
    if (!String(config.receiver || '').trim()) {
      add('notification', 'notification_receiver_required', `${field}.receiver`, '请选择通知接收人')
    }
    if (!String(config.title || '').trim()) {
      add('notification', 'notification_title_required', `${field}.title`, '通知标题不能为空')
    }
  }

  const firstSection = ADVANCED_SECTION_KEYS.find((key) => errors[key].length) || null
  return { valid: firstSection === null, errors, firstSection }
}

function isSectionConfigured(draft, section) {
  if (section === 'rules') {
    return Boolean(
      Object.keys(draft.condition_config || {}).length ||
      draft.condition_routes?.length ||
      draft.validator_config
    )
  }
  if (section === 'assignment') {
    const targetType = draft.handler_rule?.target_type || 'keep_current'
    const fallbackType = draft.handler_rule?.fallback_type || 'keep_current'
    return Boolean(
      draft.allowed_role_list?.length ||
      targetType !== 'keep_current' ||
      fallbackType !== 'keep_current' ||
      draft.handler_rule?.allow_manual_owner
    )
  }
  if (section === 'form') {
    return Boolean(
      draft.form_config?.title ||
      draft.form_config?.submit_text ||
      draft.form_config?.fields?.length
    )
  }
  if (section === 'button') return Boolean(Object.keys(draft.ui_config || {}).length)
  return Boolean(draft.trigger_config || draft.post_action_config)
}

export function advancedSectionStates(draft, states) {
  const { errors } = validateAdvancedConfig(draft, states)
  return Object.fromEntries(ADVANCED_SECTION_KEYS.map((section) => [
    section,
    errors[section].length
      ? 'invalid'
      : isSectionConfigured(draft, section)
        ? 'configured'
        : 'unconfigured'
  ]))
}

export function configuredAdvancedSectionCount(draft, states) {
  return Object.values(advancedSectionStates(draft, states))
    .filter((value) => value !== 'unconfigured')
    .length
}
