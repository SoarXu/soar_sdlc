const ENTRY_TABS = [
  { key: 'pending_handling', label: '待处理', description: '当前处理人是当前登录用户。' },
  { key: 'unassigned', label: '未分派', description: '当前处理人为空，等待认领或指派。' },
  { key: 'exception_center', label: '异常中心', description: '聚合默认工作流下需要额外关注的异常项。' },
  { key: 'following', label: '我发起/关注', description: '只展示我发起、关注或被评论提及的工作项。' },
  { key: 'project_board', label: '项目看板', description: '按迭代查看项目内需求、任务、用例和 Bug。' }
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
  bug: 'Bug',
  code_review: '代码评审'
}

const TYPE_SHORT_LABELS = {
  requirement: '需',
  task: '任',
  test_case: '测',
  bug: 'Bug',
  code_review: 'CR'
}

const STATUS_LABELS = {
  requirement: {
    pending_assignment: '待分派',
    in_processing: '处理中',
    pending_confirmation: '待确认',
    completed: '已完成',
    canceled: '已取消',
    draft: '草稿',
    active: '进行中',
    done: '已完成',
    closed: '已关闭'
  },
  task: {
    pending_assignment: '待分派',
    in_processing: '处理中',
    pending_confirmation: '待确认',
    completed: '已完成',
    canceled: '已取消',
    todo: '待办',
    doing: '进行中',
    done: '已完成',
    closed: '已关闭'
  },
  bug: {
    pending_handling: '待处理',
    fixing: '修复中',
    pending_verification: '待验证',
    verified: '已验证',
    closed: '已关闭',
    open: '打开',
    reopened: '重新打开',
    suspended: '已挂起'
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
  const keyword = String(filters.keyword || '').trim().toLowerCase()
  if (!keyword) {
    return true
  }
  const haystack = [
    item.title,
    item.project_name,
    item.exception_label
  ].filter(Boolean).join(' ').toLowerCase()
  return haystack.includes(keyword)
}

function cloneIterationWithGroups(iteration, filters = {}) {
  const groups = [
    { key: 'requirement', label: '需求', items: filterWorkbenchItems(iteration.requirements || [], filters) },
    { key: 'task', label: '任务', items: filterWorkbenchItems(iteration.tasks || [], filters) },
    { key: 'test_case', label: '测试用例', items: filterWorkbenchItems(iteration.test_cases || [], filters) },
    { key: 'bug', label: 'Bug', items: filterWorkbenchItems(iteration.bugs || [], filters) }
  ].filter((group) => !filters.types?.length || filters.types.includes(group.key))

  return {
    ...iteration,
    groups,
    visibleTotal: groups.reduce((sum, group) => sum + group.items.length, 0)
  }
}

export function buildWorkbenchViewModel(payload = {}) {
  const pending = normalizeSection('pending_handling', payload.pending_handling, '待处理', ENTRY_TABS[0].description)
  const unassigned = normalizeSection('unassigned', payload.unassigned, '未分派', ENTRY_TABS[1].description)
  const exceptionCenter = normalizeSection('exception_center', payload.exception_center, '异常中心', ENTRY_TABS[2].description)
  const trackingTabs = TRACKING_TABS.map((tab) => normalizeSection(tab.key, payload[tab.key], tab.label, tab.description))
  const trackingTotal = trackingTabs.reduce((sum, tab) => sum + tab.total, 0)
  const boardIterations = Array.isArray(payload.project_board?.iterations)
    ? payload.project_board.iterations
    : (Array.isArray(payload.iterations) ? payload.iterations : [])

  return {
    entryTabs: ENTRY_TABS,
    queueSections: [pending, unassigned, exceptionCenter],
    trackingTabs,
    queueSectionsByKey: {
      pending_handling: pending,
      unassigned: unassigned,
      exception_center: exceptionCenter
    },
    trackingTabsByKey: Object.fromEntries(trackingTabs.map((tab) => [tab.key, tab])),
    boardIterations,
    summaryCards: [
      { key: 'pending_handling', label: pending.label, value: pending.total },
      { key: 'unassigned', label: unassigned.label, value: unassigned.total },
      { key: 'exception_center', label: exceptionCenter.label, value: exceptionCenter.total },
      { key: 'following', label: '关注范围', value: trackingTotal },
      { key: 'project_board', label: '看板迭代', value: boardIterations.length }
    ],
    owners: Array.isArray(payload.owners) ? payload.owners : [],
    roleKeys: Array.isArray(payload.role_keys) ? payload.role_keys : [],
    viewMode: payload.view_mode || 'mine'
  }
}

export function filterWorkbenchItems(items = [], filters = {}) {
  return items.filter((item) => filterMatch(item, filters))
}

export function buildProjectBoard(iterations = [], filters = {}) {
  return iterations
    .map((iteration) => cloneIterationWithGroups(iteration, filters))
    .filter((iteration) => iteration.visibleTotal > 0 || !filters.hideEmpty)
}

export function isTerminalWorkItem(item = {}) {
  if (item.object_type === 'requirement') return ['completed', 'canceled', 'done', 'closed'].includes(item.status)
  if (item.object_type === 'task') return ['completed', 'canceled', 'done', 'closed'].includes(item.status)
  if (item.object_type === 'bug') return item.status === 'closed'
  return false
}

export function typeLabel(type) {
  return TYPE_LABELS[type] || type || '-'
}

export function typeShortLabel(type) {
  return TYPE_SHORT_LABELS[type] || typeLabel(type)
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
    return ['pending_handling', 'open', 'reopened'].includes(item.status) ? 'danger' : 'warning'
  }
  if (item.object_type === 'test_case') {
    if (item.last_execute_result === 'passed') return 'success'
    if (item.last_execute_result === 'failed') return 'danger'
    if (item.last_execute_result === 'blocked') return 'warning'
    return 'info'
  }
  return ['in_processing', 'active', 'doing', 'pending_confirmation'].includes(item.status) ? 'primary' : 'info'
}

export function workbenchMetaText(sectionKey, item = {}) {
  if (sectionKey === 'exception_center') {
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

  if (sectionKey === 'unassigned' && ['requirement', 'task', 'bug'].includes(item.object_type)) {
    return {
      primary: null,
      secondary: [{ key: 'auto_assign_item', label: '自动分配', type: 'warning' }]
    }
  }

  return { primary: null, secondary: [] }
}

export function formatWorkbenchDateTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-'
}
