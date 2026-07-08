import assert from 'node:assert/strict'
import {
  statusOptionsForObjectType,
  statusValueLabel
} from './workItemStatusOptions.js'

function run(name, fn) {
  try {
    fn()
    console.log(`ok - ${name}`)
  } catch (error) {
    console.error(`not ok - ${name}`)
    throw error
  }
}

run('returns selectable requirement statuses with an unrestricted option', () => {
  const options = statusOptionsForObjectType('requirement')

  assert.equal(options[0].label, '不限')
  assert.equal(options[0].value, '')
  assert.deepEqual(
    options.slice(1).map((item) => item.value),
    ['draft', 'active', 'pending_validation', 'validation_failed', 'done', 'closed']
  )
})

run('returns task and bug statuses by object type', () => {
  assert.deepEqual(
    statusOptionsForObjectType('task').slice(1).map((item) => item.value),
    ['todo', 'doing', 'done', 'closed']
  )
  assert.deepEqual(
    statusOptionsForObjectType('bug').slice(1).map((item) => item.value),
    ['open', 'fixing', 'verifying', 'closed', 'reopened', 'suspended']
  )
})

run('returns an empty list for unsupported object type', () => {
  assert.deepEqual(statusOptionsForObjectType('iteration'), [])
})

run('formats status values for transition rule tables', () => {
  assert.equal(statusValueLabel('bug', 'verifying'), '待验证')
  assert.equal(statusValueLabel('requirement', ''), '*')
  assert.equal(statusValueLabel('task', 'custom_status'), 'custom_status')
})
