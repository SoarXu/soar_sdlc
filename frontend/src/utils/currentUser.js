export function currentUserId(users) {
  const username = localStorage.getItem('current_username') || usernameFromToken() || 'admin'
  return users.find((user) => user.username === username)?.id || null
}

function usernameFromToken() {
  const token = localStorage.getItem('access_token')
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1] || ''))
    return payload.sub || null
  } catch {
    return null
  }
}
