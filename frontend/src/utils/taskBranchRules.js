export const TASK_BRANCH_OPTIONS = [
  { label: '需求实现', value: 'requirement_implementation' },
  { label: '缺陷修复', value: 'bug_fix' },
  { label: '测试支持', value: 'test_support' },
  { label: '独立事务', value: 'standalone_operation' }
]

export function deriveTaskBranch({ requirementId, currentType }) {
  if (requirementId) return 'requirement_implementation'
  return currentType || 'standalone_operation'
}

export function taskBranchLabel(value) {
  return TASK_BRANCH_OPTIONS.find((item) => item.value === value)?.label || value || '-'
}
