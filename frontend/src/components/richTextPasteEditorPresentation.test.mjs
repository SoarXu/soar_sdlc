import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const componentSource = readFileSync(new URL('./RichTextPasteEditor.vue', import.meta.url), 'utf8')
const stylesSource = readFileSync(new URL('../styles.css', import.meta.url), 'utf8')

assert.match(componentSource, /placeholder: \{ type: String, default: '可粘贴文本或截图' \}/u)

const editorStyles = stylesSource.match(/\.rich-text-paste-editor__surface \{(?<content>[\s\S]*?)\n\}/u)
assert.ok(editorStyles, 'rich-text editor surface styles must exist')
assert.match(editorStyles.groups.content, /min-height: 44px;/u)
assert.doesNotMatch(editorStyles.groups.content, /min-height: 150px;/u)
assert.match(editorStyles.groups.content, /max-height: 320px;/u)
assert.match(editorStyles.groups.content, /overflow: auto;/u)

console.log('rich-text editor presentation contracts passed')
