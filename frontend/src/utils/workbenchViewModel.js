const ENTRY_TABS = [
  { key: 'pending_handling', label: '待处理', description: '当前处理人是当前登录用户。' },
  { key: 'unassigned', label: '未分派', description: '当前处理人为空，等待认领或指派。' },
  { key: 'exception_center', label: '异常中心', description: '聚合默认工作流下需要额外关注的异常项。' },
  { key: 'following', label: '我发起/关注', description: '只显示我发起、关注或被评论提及的工作项。' }
]

const TRACKING_TABS = [
  { key: 'created_by_me', label: '我发起的', description: '由我创建、提出或上报的工作项。' },
  { key: 'watched_by_me', label: '我关注的', description: '我主动关注或被系统加入关注的工作项。' },
  { key: 'mentioned_me', label: '提到我的', description: '评论中通过 @ 提及到我的工作项。' }
]

const TYPE_LABELS = {
  requirement: '需求',
  task: '任务',
  test_case: '测试用例',
  test_run: '测试单',
  bug: '缺陷',
  code_review: '代码评审'
}

const STATUS_LABELS = {
  requirement: {
    pending_assignment: '待分派',
    in_processing: '处理中',
    pending_confirmation: '待确认',
    completed: '已完成',
    canceled: '已取消'
  },
  task: {
    pending_assignment: '待分派',
    in_processing: '处理中',
    pending_confirmation: '待确认',
    completed: '已完成',
    canceled: '已取消'
  },
  bug: {
    pending_handling: '待处理',
    fixing: '修复中',
    pending_verification: '待验证',
    verified: '已验证',
    closed: '已关闭'
  },
  test_run: {
    planning: '规划中',
    active: '进行中',
    completed: '已完成',
    canceled: '已取消',
    finished: '已结束'
  }
}

const EXECUTION_RESULT_LABELS = {
  ignored: '忽略',
  passed: '通过',
  failed: '失败',
  blocked: '阻塞'
}

function normalizeSection(key, section = {}, fallbackLabel = '', fallbackDescription = '') {
  const items = Array.isArray(section.items) ? section.items : []
  return {
    key,
    label: section.label || fallbackLabel,
    description: fallbackDescription,
    items,
    total: Number.isFinite(section.total) ? section.total : items.length
  }
}

function filterMatch(item, filters = {}) {
  const selectedTypes = new Set(filters.types || [])
  if (selectedTypes.size && !selectedTypes.has(item.object_type)) {
    return false
  }
  const scalarFilters = [
    ['projectIds', item.project_id],
    ['iterationKeys', item.iteration_group_key || (item.iteration_id ? String(item.iteration_id) : 'uniterated')],
    ['priorities', item.priority || item.severity],
    ['statuses', item.status],
    ['ownerIds', item.owner_id],
    ['handlerIds', item.handler_id]
  ]
  for (const [filterKey, value] of scalarFilters) {
    const selected = new Set(filters[filterKey] || [])
    if (selected.size && !selected.has(value)) return false
  }
  const minOverdueHours = Number(filters.minOverdueHours)
  if (Number.isFinite(minOverdueHours) && minOverdueHours > 0 && Number(item.overdue_hours || 0) < minOverdueHours) {
    return false
  }
  const keyword = String(filters.keyword || '').trim().toLowerCase()
  if (!keyword) {
    return true
  }
  const haystack = [
    item.title,
    item.project_name,
    item.iteration_name,
    item.exception_label
  ].filter(Boolean).join(' ').toLowerCase()
  return haystack.includes(keyword)
}

export function buildWorkbenchViewModel(payload = {}) {
  const pending = normalizeSection('pending_handling', payload.pending_handling, '待处理', ENTRY_TABS[0].description)
  const unassigned = normalizeSection('unassigned', payload.unassigned, '未分派', ENTRY_TABS[1].description)
  const exceptionCenter = normalizeSection('exception_center', payload.exception_center, '异常中心', ENTRY_TABS[2].description)
  const trackingTabs = TRACKING_TABS.map((tab) => normalizeSection(tab.key, payload[tab.key], tab.label, tab.description))
  const trackingTotal = trackingTabs.reduce((sum, tab) => sum + tab.total, 0)
  return {
    entryTabs: ENTRY_TABS,
    queueSections: [pending, unassigned, exceptionCenter],
    trackingTabs,
    queueSectionsByKey: {
      pending_handling: pending,
      unassigned,
      exception_center: exceptionCenter
    },
    trackingTabsByKey: Object.fromEntries(trackingTabs.map((tab) => [tab.key, tab])),
    summaryCards: [
      { key: 'pending_handling', label: pending.label, value: pending.total },
      { key: 'unassigned', label: unassigned.label, value: unassigned.total },
      { key: 'exception_center', label: exceptionCenter.label, value: exceptionCenter.total },
      { key: 'following', label: '关注范围', value: trackingTotal }
    ],
    owners: Array.isArray(payload.owners) ? payload.owners : [],
    roleKeys: Array.isArray(payload.role_keys) ? payload.role_keys : [],
    viewMode: payload.view_mode || 'mine'
  }
}

export function filterWorkbenchItems(items = [], filters = {}) {
  return items.filter((item) => filterMatch(item, filters))
}

export function isTerminalWorkItem(item = {}) {
  if (item.object_type === 'requirement') return ['completed', 'canceled'].includes(item.status)
  if (item.object_type === 'task') return ['completed', 'canceled'].includes(item.status)
  if (item.object_type === 'bug') return item.status === 'closed'
  return false
}

export function shouldShowWorkbenchWorkflowActions(sectionKey, item = {}) {
  return ['requirement', 'task', 'bug'].includes(item.object_type)
}

export function typeLabel(type) {
  return TYPE_LABELS[type] || type || '-'
}

export function typeTag(type) {
  return {
    requirement: 'primary',
    task: 'success',
    test_case: 'warning',
    bug: 'danger',
    code_review: 'info'
  }[type] || 'info'
}

export function executionResultLabel(result) {
  return EXECUTION_RESULT_LABELS[result] || result || '未执行'
}

export function itemStatusLabel(item = {}) {
  if (item.object_type === 'test_case') {
    return executionResultLabel(item.last_execute_result)
  }
  return STATUS_LABELS[item.object_type]?.[item.status] || item.status || '-'
}

export function itemStatusTag(item = {}) {
  if (isTerminalWorkItem(item)) {
    return item.status === 'closed' || item.status === 'canceled' ? 'info' : 'success'
  }
  if (item.object_type === 'bug') {
    return item.status === 'pending_handling' ? 'danger' : 'warning'
  }
  if (item.object_type === 'test_case') {
    if (item.last_execute_result === 'passed') return 'success'
    if (item.last_execute_result === 'failed') return 'danger'
    if (item.last_execute_result === 'blocked') return 'warning'
    return 'info'
  }
  return ['in_processing', 'active', 'pending_confirmation'].includes(item.status) ? 'primary' : 'info'
}

export function workbenchMetaText(sectionKey, item = {}) {
  if (sectionKey === 'exception_center') {
    if (Number(item.overdue_hours) > 0) {
      return `${item.exception_label || 'Exception'} - overdue ${item.overdue_hours}h`
    }
    return item.exception_label || '异常项'
  }
  if (sectionKey === 'watched_by_me') {
    return item.watch_source === 'mention' ? '评论提及自动关注' : '手工关注'
  }
  if (sectionKey === 'mentioned_me') {
    return item.mentioned_in_comment_id ? `评论 #${item.mentioned_in_comment_id}` : '评论提及'
  }
  return ''
}

export function workbenchItemActionGroup(sectionKey, item = {}) {
  if (item.object_type === 'test_case') {
    const secondary = ['failed', 'blocked'].includes(item.last_execute_result)
      ? [{ key: 'create_case_bug', label: '提 Bug', type: 'warning' }]
      : []
    return {
      primary: { key: 'execute_case', label: '执行', type: 'success' },
      secondary
    }
  }

  return { primary: null, secondary: [] }
}

export function workbenchInlineActions(sectionKey, item = {}) {
  const group = workbenchItemActionGroup(sectionKey, item)
  return [
    ...(group.primary ? [group.primary] : []),
    ...group.secondary
  ]
}

export function formatWorkbenchDateTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}
