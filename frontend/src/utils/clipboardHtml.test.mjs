import assert from 'node:assert/strict'
import {
  clipboardHtmlFromDataTransfer,
  getClipboardImageFiles,
  imageDataUrlToHtml,
  sanitizeHtml
} from './clipboardHtml.js'

function run(name, fn) {
  try {
    fn()
    console.log(`ok - ${name}`)
  } catch (error) {
    console.error(`not ok - ${name}`)
    throw error
  }
}

run('reads image files from clipboard files as pasted screenshots', () => {
  const png = { name: 'screenshot.png', type: 'image/png', size: 12, lastModified: 1 }
  const text = { name: 'notes.txt', type: 'text/plain', size: 4, lastModified: 1 }

  const files = getClipboardImageFiles({ files: [png, text], items: [] })

  assert.deepEqual(files, [png])
})

run('reads image files from clipboard items', () => {
  const png = { name: 'clip.png', type: 'image/png', size: 20, lastModified: 2 }

  const files = getClipboardImageFiles({
    files: [],
    items: [
      { type: 'image/png', getAsFile: () => png },
      { type: 'text/html', getAsFile: () => null }
    ]
  })

  assert.deepEqual(files, [png])
})

run('keeps safe clipboard html and strips script handlers', () => {
  const html = clipboardHtmlFromDataTransfer({
    getData: (type) => type === 'text/html' ? '<p onclick="x()">step<img src="data:image/png;base64,abc"></p><script>x()</script>' : ''
  })

  assert.equal(html, '<p>step<img src="data:image/png;base64,abc"></p>')
})

run('converts plain text paste into html with line breaks', () => {
  const html = clipboardHtmlFromDataTransfer({
    getData: (type) => type === 'text/plain' ? 'line <1>\nline 2' : ''
  })

  assert.equal(html, 'line &lt;1&gt;<br>line 2')
})

run('renders image data url as insertable html', () => {
  assert.equal(imageDataUrlToHtml('data:image/png;base64,abc'), '<img src="data:image/png;base64,abc" alt="pasted image">')
})

run('removes javascript URLs during sanitization', () => {
  assert.equal(sanitizeHtml('<a href="javascript:alert(1)">bad</a>'), '<a>bad</a>')
})
