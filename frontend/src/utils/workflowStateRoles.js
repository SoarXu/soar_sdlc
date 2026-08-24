const WORK_ITEM_OBJECT_TYPES = new Set(['requirement', 'task', 'bug'])

const WORK_ITEM_STATE_ROLE_OPTIONS = [
  { label: '待分派', value: 'unassigned' },
  { label: '待开始', value: 'waiting_iteration' },
  { label: '执行中', value: 'active_work' }
]

export function stateRoleOptions(objectType) {
  return WORK_ITEM_OBJECT_TYPES.has(objectType) ? WORK_ITEM_STATE_ROLE_OPTIONS : []
}
