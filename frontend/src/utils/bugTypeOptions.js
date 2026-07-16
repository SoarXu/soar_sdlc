export const DEFAULT_BUG_TYPE_KEY = 'code_issue'

export function toBugTypeOptions(rows = []) {
  return rows.map((item) => ({
    value: item.type_key,
    label: item.display_name,
    isRealBug: item.is_real_bug,
    defaultTargetStatus: item.default_target_status
  }))
}
