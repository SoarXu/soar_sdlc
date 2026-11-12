import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./WorkflowActionButtons.vue', import.meta.url), 'utf8')
const body = source.match(/function normalizeReviewActions\(source\) \{([\s\S]*?)\n\}/)[1]
const normalize = new Function('source', body)
for (const action_key of ['approve_review', 'reject_review']) {
  const other = { action_key: 'edit', transition_id: 1 }
  const result = normalize([other, { action_key, transition_id: 2 }])
  assert.equal(result.length, 2)
  assert.equal(result[0], other)
  assert.equal(result[1].action_key, 'review_work_item')
}
assert.deepEqual(normalize([]), [])
assert.equal(normalize([
  { action_key: 'approve_review' }, { action_key: 'reject_review' },
]).length, 1)
console.log('review action permission tests passed')
