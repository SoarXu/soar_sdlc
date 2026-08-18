import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const dialogSource = await readFile(new URL('./WorkItemReviewDialog.vue', import.meta.url), 'utf8')
const apiSource = await readFile(new URL('../api/devops.js', import.meta.url), 'utf8')

assert.match(dialogSource, /CommitDiffViewer/)
assert.match(dialogSource, /未找到 Git Diff 片段/)
assert.match(dialogSource, /fetchWorkItemReviewContext/)
assert.match(dialogSource, /decideWorkItemReview/)
assert.match(dialogSource, /请填写不通过理由/)
assert.match(dialogSource, /评审通过/)
assert.match(dialogSource, /评审不通过/)
assert.match(apiSource, /submitWorkItemReview/)
assert.match(apiSource, /fetchWorkItemReviewContext/)

console.log('work item review dialog tests passed')
