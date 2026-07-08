import assert from 'node:assert/strict'

import {
  actionErrorMessage,
  canConfigureWorkflow,
  canCreateWorkItem,
  canDeleteProject,
  canDeleteWorkItem,
  canExecuteWorkItem,
  canManageProject,
  canManageTestCase,
  currentUserFromStorage,
  isDelegateReasonRequiredError,
  isProjectOwner,
  isSystemAdmin
} from './permissions.js'

const admin = { id: 1, username: 'admin', roles: [{ role_key: 'system_admin', enabled: true }] }
const owner = { id: 2, username: 'owner', roles: [] }
const member = { id: 3, username: 'dev', roles: [] }
const tester = { id: 4, username: 'qa', roles: [] }
const outsider = { id: 5, username: 'guest', roles: [] }
const globalProjectOwner = { id: 6, username: 'po', roles: [{ role_key: 'project_owner', enabled: true }] }

const project = { id: 10, owner_id: owner.id }
const members = [
  { project_id: project.id, user_id: member.id, project_role: 'developer' },
  { project_id: project.id, user_id: tester.id, project_role: 'tester' },
  { project_id: project.id, user_id: globalProjectOwner.id, project_role: 'developer' }
]

{
  assert.equal(isSystemAdmin(admin), true)
  assert.equal(isSystemAdmin({ ...admin, roles: [{ role_key: 'system_admin', enabled: false }] }), false)
  assert.equal(canConfigureWorkflow(admin), true)
  assert.equal(canConfigureWorkflow(owner), false)
}

{
  assert.equal(isProjectOwner(project, owner, members), true)
  assert.equal(isProjectOwner(project, globalProjectOwner, members), true)
  assert.equal(isProjectOwner(project, member, members), false)
  assert.equal(canManageProject(project, admin, members), true)
  assert.equal(canManageProject(project, owner, members), true)
  assert.equal(canManageProject(project, member, members), false)
  assert.equal(canDeleteProject(admin), true)
  assert.equal(canDeleteProject(owner), false)
}

{
  assert.equal(canCreateWorkItem(project, admin, members), true)
  assert.equal(canCreateWorkItem(project, owner, members), true)
  assert.equal(canCreateWorkItem(project, member, members), true)
  assert.equal(canCreateWorkItem(project, outsider, members), false)
  assert.equal(canDeleteWorkItem(project, owner, members), true)
  assert.equal(canDeleteWorkItem(project, member, members), false)
}

{
  const item = { id: 100, project_id: project.id, owner_id: member.id }
  assert.equal(canExecuteWorkItem(item, member, project, members), true)
  assert.equal(canExecuteWorkItem(item, owner, project, members), true)
  assert.equal(canExecuteWorkItem(item, admin, project, members), true)
  assert.equal(canExecuteWorkItem(item, tester, project, members), false)
}

{
  assert.equal(canManageTestCase(project, tester, members), true)
  assert.equal(canManageTestCase(project, member, members), false)
  assert.equal(canManageTestCase(project, owner, members), true)
}

{
  const originalLocalStorage = globalThis.localStorage
  const storage = new Map([
    ['current_user_id', '3'],
    ['current_username', 'dev']
  ])
  globalThis.localStorage = { getItem: (key) => storage.get(key) || null }
  assert.deepEqual(currentUserFromStorage([admin, member]), member)
  globalThis.localStorage = originalLocalStorage
}

{
  assert.equal(actionErrorMessage({ response: { data: { detail: '无权操作' } } }, '保存失败'), '无权操作')
  assert.equal(
    actionErrorMessage({ response: { data: { detail: '新当前处理人不是对象所属项目成员' } } }, '认领失败'),
    '你不是该项目成员，无法认领。请联系项目负责人加入项目。'
  )
  assert.equal(
    actionErrorMessage({ response: { data: { detail: '处理人必须是对象所属项目成员' } } }, '认领失败'),
    '你不是该项目成员，无法认领。请联系项目负责人加入项目。'
  )
  assert.equal(
    actionErrorMessage({ response: { data: { detail: '处理人必须是对象所属项目成员' } } }, '指派失败'),
    '当前处理人必须是该工作项所属项目成员，请先将该用户加入项目成员后再指派。'
  )
  assert.equal(
    actionErrorMessage({ response: { data: { detail: 'Delegate reason is required' } } }, '激活失败'),
    '请填写代处理原因'
  )
  assert.equal(isDelegateReasonRequiredError({ response: { data: { detail: 'Delegate reason is required' } } }), true)
  assert.equal(isDelegateReasonRequiredError({ response: { data: { detail: '其他错误' } } }), false)
  assert.equal(actionErrorMessage({}, '保存失败'), '保存失败')
}

console.log('permissions tests passed')
