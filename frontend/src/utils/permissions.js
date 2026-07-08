export const SYSTEM_ADMIN_ROLE_KEYS = new Set(['system_admin'])
export const PROJECT_OWNER_ROLE_KEYS = new Set(['project_owner'])
export const PROJECT_OWNER_PROJECT_ROLES = new Set(['project_owner'])
export const TEST_PROJECT_ROLES = new Set(['tester', 'test_lead', 'qa', 'quality_assurance'])

export function currentUserFromStorage(users = []) {
  const storedId = Number(globalThis.localStorage?.getItem('current_user_id') || 0)
  if (storedId) {
    const byId = users.find((user) => Number(user.id) === storedId)
    if (byId) return byId
  }
  const username = globalThis.localStorage?.getItem('current_username') || usernameFromToken()
  if (!username) return null
  return users.find((user) => user.username === username) || null
}

export function isSystemAdmin(user) {
  return hasEnabledRole(user, SYSTEM_ADMIN_ROLE_KEYS)
}

export function isProjectOwner(project, user, members = []) {
  const userId = normalizedId(user?.id)
  if (!project || !userId) return false
  const projectId = normalizedId(project.id)
  if (normalizedId(project.owner_id) === userId) return true
  if (hasProjectRole(members, projectId, userId, PROJECT_OWNER_PROJECT_ROLES)) return true
  return hasEnabledRole(user, PROJECT_OWNER_ROLE_KEYS) && isProjectMember(members, projectId, userId)
}

export function isProjectMember(members = [], projectOrId, userOrId) {
  const projectId = normalizedId(typeof projectOrId === 'object' ? projectOrId?.id : projectOrId)
  const userId = normalizedId(typeof userOrId === 'object' ? userOrId?.id : userOrId)
  if (!projectId || !userId) return false
  return members.some((member) => normalizedId(member.project_id) === projectId && normalizedId(member.user_id) === userId)
}

export function canManageProject(project, user, members = []) {
  return isSystemAdmin(user) || isProjectOwner(project, user, members)
}

export function canDeleteProject(user) {
  return isSystemAdmin(user)
}

export function canConfigureWorkflow(user) {
  return isSystemAdmin(user)
}

export function canCreateWorkItem(project, user, members = []) {
  return isSystemAdmin(user) || isProjectOwner(project, user, members) || isProjectMember(members, project, user)
}

export function canDeleteWorkItem(project, user, members = []) {
  return isSystemAdmin(user) || isProjectOwner(project, user, members)
}

export function canExecuteWorkItem(item, user, project = null, members = []) {
  const userId = normalizedId(user?.id)
  if (!userId) return false
  if (normalizedId(item?.owner_id) === userId) return true
  return isSystemAdmin(user) || isProjectOwner(project || { id: item?.project_id || item?.source_project_id }, user, members)
}

export function canManageTestCase(project, user, members = []) {
  return (
    isSystemAdmin(user)
    || isProjectOwner(project, user, members)
    || hasProjectRole(members, normalizedId(project?.id), normalizedId(user?.id), TEST_PROJECT_ROLES)
  )
}

export function actionErrorMessage(error, fallback = '操作失败') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || item.message || String(item)).join('；')
  return friendlyErrorMessage(detail || error?.message, fallback) || fallback
}

export function isDelegateReasonRequiredError(error) {
  const detail = error?.response?.data?.detail || error?.message
  return String(detail || '') === 'Delegate reason is required' || String(detail || '') === '请填写代处理原因'
}

function friendlyErrorMessage(message, fallback = '') {
  if (!message) return ''
  const text = String(message)
  if (text === 'Delegate reason is required') {
    return '请填写代处理原因'
  }
  if ((text === '新当前处理人不是对象所属项目成员' || text === '处理人必须是对象所属项目成员') && fallback.includes('认领')) {
    return '你不是该项目成员，无法认领。请联系项目负责人加入项目。'
  }
  if (text === '新当前处理人不是对象所属项目成员' || text === '处理人必须是对象所属项目成员') {
    return '当前处理人必须是该工作项所属项目成员，请先将该用户加入项目成员后再指派。'
  }
  if (text === 'Work item already assigned') {
    return '该工作项已被认领或指派，请刷新工作台后查看最新状态。'
  }
  if (text === 'Terminal work item cannot be assigned') {
    return '该工作项已完成或已关闭，不能再认领或指派。'
  }
  if (text === 'No auto assignment target found') {
    return '没有找到符合规则的自动分配对象，请手动选择项目成员进行指派。'
  }
  return text
}

function hasEnabledRole(user, roleKeys) {
  return Boolean(user?.roles?.some((role) => role.enabled !== false && roleKeys.has(role.role_key)))
}

function hasProjectRole(members = [], projectId, userId, projectRoles) {
  if (!projectId || !userId) return false
  return members.some((member) => (
    normalizedId(member.project_id) === projectId
    && normalizedId(member.user_id) === userId
    && projectRoles.has(member.project_role)
  ))
}

function normalizedId(value) {
  const id = Number(value)
  return Number.isFinite(id) && id > 0 ? id : null
}

function usernameFromToken() {
  const token = globalThis.localStorage?.getItem('access_token')
  if (!token) return null
  try {
    const payload = JSON.parse(globalThis.atob(token.split('.')[1] || ''))
    return payload.sub || null
  } catch {
    return null
  }
}
