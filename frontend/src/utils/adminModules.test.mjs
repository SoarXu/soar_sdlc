import test from 'node:test'
import assert from 'node:assert/strict'

import { activeAdminMenuIndex, adminModules, isAdminPath } from './adminModules.js'

test('admin modules keep the expected backend order', () => {
  assert.deepEqual(
    adminModules.map((item) => item.path),
    ['/roles', '/workflow', '/exception-rules', '/admin/ldap']
  )
})

test('admin modules expose stable card titles', () => {
  assert.deepEqual(
    adminModules.slice(0, 2).map((item) => item.title),
    ['用户管理', '工作流配置']
  )
})

test('exception rules expose a stable admin card', () => {
  assert.deepEqual(adminModules[2], {
    key: 'exception_rules',
    title: '异常规则',
    description: '配置工作台异常识别阈值与适用范围。',
    navGroupPath: '/admin',
    path: '/exception-rules'
  })
})

test('LDAP exposes a stable admin card', () => {
  assert.deepEqual(adminModules.at(-1), {
    key: 'ldap',
    title: 'LDAP 集成',
    description: '配置目录服务连接与用户属性映射。',
    navGroupPath: '/admin',
    path: '/admin/ldap'
  })
})

test('admin route helper recognizes overview and child pages', () => {
  assert.equal(isAdminPath('/admin'), true)
  assert.equal(isAdminPath('/roles'), true)
  assert.equal(isAdminPath('/workflow'), true)
  assert.equal(isAdminPath('/exception-rules'), true)
  assert.equal(isAdminPath('/admin/ldap'), true)
  assert.equal(isAdminPath('/projects'), false)
})

test('admin active menu helper maps backend routes to the group index', () => {
  assert.equal(activeAdminMenuIndex('/admin'), '/admin')
  assert.equal(activeAdminMenuIndex('/roles'), '/admin')
  assert.equal(activeAdminMenuIndex('/workflow'), '/admin')
  assert.equal(activeAdminMenuIndex('/exception-rules'), '/admin')
  assert.equal(activeAdminMenuIndex('/admin/ldap'), '/admin')
  assert.equal(activeAdminMenuIndex('/projects'), null)
})

test('admin modules stay grouped under the single admin navigation entry', () => {
  assert.deepEqual(
    adminModules.slice(0, 2).map((item) => item.navGroupPath),
    ['/admin', '/admin']
  )
})
