import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const rolesViewSource = readFileSync(new URL('./RolesView.vue', import.meta.url), 'utf8')
const workflowViewSource = readFileSync(new URL('./WorkflowView.vue', import.meta.url), 'utf8')
const adminViewSource = readFileSync(new URL('./AdminView.vue', import.meta.url), 'utf8')

test('roles view exposes a stable backToAdmin action', () => {
  assert.match(rolesViewSource, /@click="backToAdmin"/)
  assert.match(rolesViewSource, /function backToAdmin\(/)
})

test('workflow view exposes a stable backToAdmin action', () => {
  assert.match(workflowViewSource, /@click="backToAdmin"/)
  assert.match(workflowViewSource, /function backToAdmin\(/)
})

test('admin overview cards expose a card-level navigation action', () => {
  assert.match(adminViewSource, /@click="openModule\(module\.path\)"/)
  assert.match(adminViewSource, /function openModule\(path\)/)
  assert.doesNotMatch(adminViewSource, /<el-button type="primary"/)
})
