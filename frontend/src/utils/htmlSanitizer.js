import createDOMPurify from 'dompurify'

const purifier = typeof window !== 'undefined' && window.document ? createDOMPurify(window) : null

export function sanitizeHtml(value = '') {
  if (!purifier) throw new Error('HTML sanitizer requires a DOM window')
  return purifier.sanitize(String(value), {
    FORBID_TAGS: ['svg', 'math', 'script', 'style', 'iframe', 'object', 'embed']
  })
}
