import { sanitizeHtml } from './htmlSanitizer.js'

export function syncRichTextEditorValue(editor, modelValue) {
  const sanitized = sanitizeHtml(modelValue || '')
  if (editor && editor.innerHTML !== sanitized) editor.innerHTML = sanitized
  return sanitized
}
