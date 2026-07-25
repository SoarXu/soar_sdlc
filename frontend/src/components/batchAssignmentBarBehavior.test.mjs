import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./BatchAssignmentBar.vue', import.meta.url), 'utf8')

assert.match(source, /已选\s*\{\{ selectedRows\.length \}\}\s*项/)
assert.match(source, /<el-button[^>]*@click="dialogVisible = true"/)
assert.match(source, /<el-dialog[^>]*append-to-body/)
assert.match(source, /<el-select v-model="nextOwnerId"[^>]*filterable/)
assert.match(source, /v-if="reasonRequired"[^>]*label="代处理原因"/)
assert.match(source, /:loading="submitting"/)
assert.match(source, /executeWorkflowBulkAssignment/)
assert.match(source, /emit\('completed', data\)/)
assert.match(source, /emit\('error', error\)/)

console.log('batch assignment bar behavior tests passed')
