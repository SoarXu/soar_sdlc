import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const styles = await readFile(new URL('../styles.css', import.meta.url), 'utf8')

assert.match(
  styles,
  /\.project-list-actions \.workflow-action-buttons-list \.el-button\s*\{[\s\S]*?height:\s*30px;[\s\S]*?min-height:\s*30px;[\s\S]*?padding:\s*0 6px;[\s\S]*?font-size:\s*14px;[\s\S]*?line-height:\s*23px;/,
  '项目集树和项目列表的工作流按钮必须与直接按钮使用相同盒模型',
)

console.log('project list action sizing contract passed')
