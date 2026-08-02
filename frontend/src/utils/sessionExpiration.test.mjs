import assert from 'node:assert/strict'

import { createSessionExpirationHandler } from './sessionExpiration.js'

const sessionKeys = [
  'access_token',
  'current_username',
  'current_full_name',
  'current_full_name_username',
  'current_user_id',
  'must_change_password'
]

function createStorage() {
  const values = new Map(sessionKeys.map((key) => [key, 'stored-value']))
  return {
    getItem: (key) => values.get(key) || null,
    removeItem: (key) => values.delete(key),
    values
  }
}

{
  const storage = createStorage()
  const notices = []
  const navigations = []
  const handleSessionExpired = createSessionExpirationHandler({
    storage,
    notify: async (message) => notices.push(message),
    navigate: async (location) => navigations.push(location),
    getCurrentPath: () => '/projects/7?tab=members'
  })

  await handleSessionExpired('/projects')

  assert.deepEqual([...storage.values.keys()], [])
  assert.deepEqual(notices, ['登录状态已失效，请重新登录'])
  assert.deepEqual(navigations, [{ name: 'login', query: { redirect: '/projects/7?tab=members' } }])
}

{
  const storage = createStorage()
  const notices = []
  const navigations = []
  const handleSessionExpired = createSessionExpirationHandler({
    storage,
    notify: async (message) => notices.push(message),
    navigate: async (location) => navigations.push(location),
    getCurrentPath: () => '/login'
  })

  await handleSessionExpired('/auth/login')

  assert.equal(storage.getItem('access_token'), 'stored-value')
  assert.deepEqual(notices, [])
  assert.deepEqual(navigations, [])
}

{
  const storage = createStorage()
  let resolveNotice
  let noticeCount = 0
  let navigationCount = 0
  const handleSessionExpired = createSessionExpirationHandler({
    storage,
    notify: () => {
      noticeCount += 1
      return new Promise((resolve) => {
        resolveNotice = resolve
      })
    },
    navigate: async () => {
      navigationCount += 1
    },
    getCurrentPath: () => '/dashboard'
  })

  const firstRequest = handleSessionExpired('/workbench')
  const secondRequest = handleSessionExpired('/users')
  assert.equal(noticeCount, 1)
  resolveNotice()
  await Promise.all([firstRequest, secondRequest])

  assert.equal(navigationCount, 1)
}

console.log('session expiration tests passed')
