import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { JSDOM } from 'jsdom'

globalThis.window = new JSDOM('<!doctype html><html><body><div id="editor"></div></body></html>').window

const { syncRichTextEditorValue } = await import('./richTextEditorModel.js')
const editor = window.document.querySelector('#editor')
const malicious = '<img src=x onerror=alert(1)><a href="&#x6a;avascript:alert(2)">link</a><svg><script>alert(3)</script></svg><p>safe</p>'

const sanitized = syncRichTextEditorValue(editor, malicious)

assert.equal(sanitized, '<img src="x"><a>link</a><p>safe</p>')
assert.equal(editor.innerHTML, sanitized)
assert.equal(editor.querySelector('[onerror]'), null)
assert.equal(editor.querySelector('svg'), null)
assert.equal(editor.querySelector('a').hasAttribute('href'), false)

const componentSource = await readFile(new URL('../components/RichTextPasteEditor.vue', import.meta.url), 'utf8')
assert.match(componentSource, /syncRichTextEditorValue\(editor, value\)/u)
assert.doesNotMatch(componentSource, /editor\.innerHTML\s*=\s*value/u)

console.log('rich-text editor model synchronization contracts passed')
