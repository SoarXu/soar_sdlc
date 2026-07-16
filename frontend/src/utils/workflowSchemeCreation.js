const LIFECYCLE_META = {
  draft: { label: '草稿', type: 'warning' },
  enabled: { label: '已启用', type: 'success' },
  disabled: { label: '已停用', type: 'info' }
}

export function lifecycleStatusMeta(status) {
  return LIFECYCLE_META[status] || { label: status || '未知', type: 'info' }
}

export function templateSourceValue(source) {
  return `${source.source_type}:${source.source_id}`
}

export function groupWorkflowTemplateSources(sources = []) {
  const groupDefinitions = [
    { sourceType: 'system', label: '系统模板' },
    { sourceType: 'scheme', label: '已有方案' }
  ]
  return groupDefinitions.map((group) => ({
    label: group.label,
    options: sources
      .filter((source) => source.source_type === group.sourceType)
      .map((source) => ({
        ...source,
        value: templateSourceValue(source),
        source_type_label: group.label === '系统模板' ? '系统模板' : '已有方案'
      }))
  })).filter((group) => group.options.length)
}

export function buildWorkflowSchemeCreatePayload(form) {
  const payload = {
    name: form.name.trim(),
    description: form.description?.trim() || null,
    creation_mode: form.creation_mode
  }
  if (form.creation_mode === 'template') {
    const separatorIndex = form.template_source_value.indexOf(':')
    payload.template_source = {
      source_type: form.template_source_value.slice(0, separatorIndex),
      source_id: form.template_source_value.slice(separatorIndex + 1)
    }
  }
  return payload
}

export function workflowSchemeActionErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail
  if (detail?.project_count) {
    return `该方案仍关联 ${detail.project_count} 个项目，请先将这些项目切换到其他已启用方案。`
  }
  if (detail?.invalid_object_types?.length) {
    const labels = { requirement: '需求', task: '任务', bug: 'Bug' }
    const types = detail.invalid_object_types.map((type) => labels[type] || type).join('、')
    return `${types}工作流尚未满足启用条件，请检查流程节点、流转边和初始状态。`
  }
  return fallback
}
