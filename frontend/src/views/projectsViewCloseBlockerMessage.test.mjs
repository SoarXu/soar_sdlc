import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProjectsView.vue', import.meta.url), 'utf8')
const statusHandler = source.slice(
  source.indexOf('async function changeProjectStatus'),
  source.indexOf('async function submitStatusOperation')
)

assert.match(
  source,
  /function isUnfinishedIterationBlocker\(error\) \{[\s\S]*?PROJECT_HAS_UNFINISHED_ITEMS/,
  'Project close blocker detection must recognize the iteration blocker returned by the API'
)

const iterationBlockerBranch = statusHandler.match(
  /if \(isUnfinishedIterationBlocker\(error\)\) \{(?<content>[\s\S]*?)\} else \{/
)

assert.ok(iterationBlockerBranch, 'Project status errors must have a dedicated iteration-blocker branch')
assert.match(iterationBlockerBranch.groups.content, /ElMessage\.warning\('项目存在未结束迭代，无法关闭。'\)/)
assert.doesNotMatch(iterationBlockerBranch.groups.content, /showActionError/)

console.log('project close iteration blocker message contract passed')
