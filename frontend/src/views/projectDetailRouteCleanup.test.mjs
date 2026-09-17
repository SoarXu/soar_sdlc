import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')

assert.match(
  source,
  /delete\s+query\[`\$\{key\}_page`\]/,
  '同步项目列表状态前应删除旧的分页参数，避免第一页仍残留旧页码'
)

console.log('project detail route cleanup contract passed')
