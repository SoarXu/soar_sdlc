import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProgramsView.vue', import.meta.url), 'utf8')

assert.match(
  source,
  /await deleteProgram\(id\)\s*\n\s*ElMessage\.success\('项目集删除成功'\)\s*\n\s*await loadData\(\)/,
)

console.log('program delete success message contract passed')
