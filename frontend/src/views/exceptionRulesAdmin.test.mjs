import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const apiSource = readFileSync(new URL('../api/exceptionRules.js', import.meta.url), 'utf8')
const viewSource = readFileSync(new URL('./ExceptionRulesView.vue', import.meta.url), 'utf8')

assert.match(apiSource, /\/exception-rules/)
assert.match(viewSource, /threshold_hours/)
assert.match(viewSource, /threshold_count/)
assert.match(viewSource, /enabled/)
assert.match(viewSource, /project_id/)
assert.match(viewSource, /object_type/)
assert.match(viewSource, /priority/)
assert.match(viewSource, /status/)

console.log('exception rule admin tests passed')
