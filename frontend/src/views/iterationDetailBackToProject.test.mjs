import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = (await readFile(new URL('./IterationDetailView.vue', import.meta.url), 'utf8')).replace(/\r\n/g, '\n')

assert.match(
  source,
  /<el-button v-if="sourceProjectId"[^>]*@click="backToSourceProject"[^>]*>回到项目<\/el-button>/,
  'project return button must only render for a valid source project'
)
assert.doesNotMatch(
  source,
  /ArrowLeft|:icon="ArrowLeft"/,
  'project return button must not render a leading arrow icon'
)
assert.match(
  source,
  /const sourceProjectId = computed\(\(\) => \{[\s\S]*route\.query\.from !== 'project'[\s\S]*Number\(route\.query\.projectId\)[\s\S]*Number\.isInteger\(projectId\) && projectId > 0/,
  'source project id must be derived defensively from route query context'
)
assert.match(
  source,
  /function backToSourceProject\(\) \{\s*if \(!sourceProjectId\.value\) return\s*router\.push\(\{\s*name: 'project-detail',\s*params: \{ id: sourceProjectId\.value \},\s*query: \{ tab: 'iterations' \}\s*\}\)\s*\}/,
  'project return must target the source project iteration tab'
)

console.log('iteration detail back-to-project contract passed')
