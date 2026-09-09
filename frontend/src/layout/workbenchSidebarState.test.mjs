import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { saveWorkbenchQuery } from '../utils/workbenchSidebarState.js'

const source = await readFile(new URL('./MainLayout.vue', import.meta.url), 'utf8')

test('sidebar workbench navigation reuses the last dashboard query', () => {
  assert.match(source, /workbenchMenuTarget/)
  assert.match(source, /saveWorkbenchQuery/)
})

test('saving dashboard query tolerates unavailable session storage', () => {
  const originalStorage = globalThis.sessionStorage
  Object.defineProperty(globalThis, 'sessionStorage', {
    configurable: true,
    value: { setItem() { throw new Error('storage denied') } }
  })
  try {
    assert.doesNotThrow(() => saveWorkbenchQuery({ page: 2 }))
  } finally {
    Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: originalStorage })
  }
})
