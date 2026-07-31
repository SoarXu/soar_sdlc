import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const styles = await readFile(new URL('../styles.css', import.meta.url), 'utf8')

for (const selector of [
  '.project-list-actions .el-button',
  '.project-list-actions .workflow-action-buttons-list .el-button',
]) {
  assert.match(
    styles,
    new RegExp(`${selector.replace(/\./g, '\\.')}\\s*\\{[\\s\\S]*?height:\\s*30px;[\\s\\S]*?min-height:\\s*30px;[\\s\\S]*?padding:\\s*0 6px;[\\s\\S]*?line-height:\\s*23px;`),
    `${selector} must match the status text line height without changing the button box height`,
  )
}

console.log('project list action line-height contract passed')
