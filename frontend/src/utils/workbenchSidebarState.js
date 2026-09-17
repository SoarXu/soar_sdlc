import { parseWorkbenchRouteState, serializeWorkbenchRouteState } from './workbenchRouteState.js'

const STORAGE_PREFIX = 'workbench:last-query:'

function storageKey() {
  const username = typeof localStorage !== 'undefined'
    ? localStorage.getItem('current_username') || 'anonymous'
    : 'anonymous'
  return `${STORAGE_PREFIX}${username}`
}

export function saveWorkbenchQuery(query = {}) {
  if (typeof sessionStorage === 'undefined') return
  const normalized = serializeWorkbenchRouteState(parseWorkbenchRouteState(query))
  try {
    sessionStorage.setItem(storageKey(), JSON.stringify(normalized))
  } catch {
    // Storage may be unavailable in private mode or when quota is exhausted.
  }
}

export function loadWorkbenchQuery() {
  if (typeof sessionStorage === 'undefined') return {}
  try {
    const value = JSON.parse(sessionStorage.getItem(storageKey()) || '{}')
    return value && typeof value === 'object' ? value : {}
  } catch {
    return {}
  }
}

export function workbenchMenuTarget() {
  const query = loadWorkbenchQuery()
  const search = new URLSearchParams(query).toString()
  return search ? `/?${search}` : '/'
}
