export const workItemStatusOptions = {
  requirement: [
    { label: '草稿', value: 'draft' },
    { label: '激活', value: 'active' },
    { label: '待验证', value: 'pending_validation' },
    { label: '验证未通过', value: 'validation_failed' },
    { label: '完成', value: 'done' },
    { label: '关闭', value: 'closed' }
  ],
  task: [
    { label: '待办', value: 'todo' },
    { label: '进行中', value: 'doing' },
    { label: '完成', value: 'done' },
    { label: '关闭', value: 'closed' }
  ],
  bug: [
    { label: '待确认', value: 'open' },
    { label: '修复中', value: 'fixing' },
    { label: '待验证', value: 'verifying' },
    { label: '已关闭', value: 'closed' },
    { label: '重新打开', value: 'reopened' },
    { label: '已挂起', value: 'suspended' }
  ]
}

export function statusOptionsForObjectType(objectType, includeUnrestricted = true) {
  const options = workItemStatusOptions[objectType]
  if (!options) return []
  return includeUnrestricted ? [{ label: '不限', value: '' }, ...options] : options
}

export function statusValueLabel(objectType, value) {
  if (!value) return '*'
  return workItemStatusOptions[objectType]?.find((item) => item.value === value)?.label || value
}
