const unsafeTagsPattern = /<(script|style|iframe|object|embed)\b[\s\S]*?<\/\1>/gi
const unsafeSelfClosingPattern = /<(script|style|iframe|object|embed)\b[^>]*\/?>/gi
const eventAttributePattern = /\s+on[a-z]+\s*=\s*(".*?"|'.*?'|[^\s>]+)/gi
const javascriptUrlPattern = /\s+(href|src)\s*=\s*(['"]?)javascript:[\s\S]*?\2/gi

export function sanitizeHtml(value = '') {
  return String(value)
    .replace(unsafeTagsPattern, '')
    .replace(unsafeSelfClosingPattern, '')
    .replace(eventAttributePattern, '')
    .replace(javascriptUrlPattern, '')
}

export function clipboardHtmlFromDataTransfer(dataTransfer) {
  if (!dataTransfer) return ''

  const html = dataTransfer.getData?.('text/html')
  if (html) return sanitizeHtml(html)

  const text = dataTransfer.getData?.('text/plain')
  return text ? escapeHtml(text).replace(/\r?\n/g, '<br>') : ''
}

export function getClipboardImageFiles(dataTransfer) {
  const files = Array.from(dataTransfer?.files || []).filter((file) => file.type?.startsWith('image/'))
  const itemFiles = Array.from(dataTransfer?.items || [])
    .filter((item) => item.type?.startsWith('image/'))
    .map((item) => item.getAsFile?.())
    .filter(Boolean)

  const seen = new Set()
  return [...files, ...itemFiles].filter((file) => {
    const key = `${file.name || ''}:${file.type || ''}:${file.size || 0}:${file.lastModified || 0}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function imageDataUrlToHtml(dataUrl) {
  return `<img src="${escapeAttribute(dataUrl)}" alt="pasted image">`
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function escapeAttribute(value) {
  return String(value).replace(/"/g, '&quot;')
}
