const SESSION_KEYS = [
  'access_token',
  'current_username',
  'current_full_name',
  'current_full_name_username',
  'current_user_id',
  'must_change_password'
]

export function createSessionExpirationHandler({ storage, notify, navigate, getCurrentPath }) {
  let inProgress = null

  return async function handleSessionExpired(requestUrl) {
    if (isLoginRequest(requestUrl)) return false
    if (inProgress) return inProgress

    const redirect = getCurrentPath()
    inProgress = (async () => {
      SESSION_KEYS.forEach((key) => storage.removeItem(key))
      await notify('登录状态已失效，请重新登录')

      if (redirect !== '/login') {
        await navigate({ name: 'login', query: { redirect } })
      }
      return true
    })()

    try {
      return await inProgress
    } finally {
      inProgress = null
    }
  }
}

function isLoginRequest(requestUrl) {
  return String(requestUrl || '').split('?')[0].endsWith('/auth/login')
}
