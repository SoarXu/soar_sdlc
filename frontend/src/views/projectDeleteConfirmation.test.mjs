import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProjectsView.vue', import.meta.url), 'utf8')

assert.doesNotMatch(source, /<el-popconfirm/)
assert.match(source, /@click="confirmRemoveProject\(row\.id\)"/)

const confirmBlock = source.match(/async function confirmRemoveProject\(id\) \{[\s\S]*?\n\}/)?.[0] || ''
assert.match(confirmBlock, /await ElMessageBox\.confirm\('确认删除该项目？子项目将一并删除。', '提示', \{ type: 'warning' \}\)/)
assert.match(confirmBlock, /await removeProject\(id\)/)

console.log('project delete confirmation tests passed')
