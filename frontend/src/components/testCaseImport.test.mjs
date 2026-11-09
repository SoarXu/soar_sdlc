import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, reactive, ref, watch, nextTick } from 'vue'

const source = await readFile(new URL('./TestCaseImportDialog.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
const factory = new Function('computed', 'reactive', 'ref', 'watch', 'ElMessage', 'showActionError', 'downloadTestCaseImportTemplate', 'previewTestCaseImport', 'commitTestCaseImport', 'defineProps', 'defineEmits', 'defineExpose', `${script}\nreturn { open, projectId, defaultRequirementId, file, preview, overrides, duplicateStrategy, ready, runPreview, commit, onFileChange, setAssociation, visible }`)
const calls = [], events = []
let resolvePreview
const vm = factory(computed, reactive, ref, watch, { warning() {}, success() {} }, () => {}, () => {},
  async (...args) => { calls.push(['preview', ...args]); return await new Promise(resolve => { resolvePreview = resolve }) },
  async (...args) => { calls.push(['commit', ...args]); return { data: { created_count: 2, skipped_count: 0 } } },
  () => ({ projects: [{ id: 1 }, { id: 2 }], requirements: [{ id: 10, project_id: 1 }], lockProject: false }),
  () => (...args) => events.push(args), () => {})

vm.open(1, 10)
await nextTick()
assert.equal(vm.defaultRequirementId.value, 10)
vm.onFileChange({ raw: { name: 'cases.xlsx', size: 1024 } })
assert.equal(vm.ready.value, false)
await vm.commit()
assert.equal(calls.length, 0, '没有预检不得提交')
const pending = vm.runPreview()
resolvePreview({ data: { error_count: 0, rows: [], requirement_groups: [] } })
await pending
assert.equal(vm.ready.value, true)
vm.defaultRequirementId.value = null
assert.equal(vm.ready.value, false, '更改默认需求后必须重新预检')
vm.defaultRequirementId.value = 10
vm.duplicateStrategy.value = 'create_duplicate'
assert.equal(vm.ready.value, false, '更改重复策略后必须重新预检')
vm.duplicateStrategy.value = 'skip'
vm.setAssociation('重名需求', 10)
assert.equal(vm.ready.value, false, '更改关联后必须重新预检')
assert.equal(vm.overrides['重名需求'], 10)
const next = vm.runPreview()
resolvePreview({ data: { error_count: 0, rows: [], requirement_groups: [] } })
await next
await vm.commit()
assert.equal(calls.filter(call => call[0] === 'commit').length, 1)
assert.equal(events[0][0], 'completed')
assert.equal(vm.visible.value, false)
vm.onFileChange({ raw: { name: 'replacement.xlsx', size: 1024 } })
assert.equal(vm.ready.value, false)
assert.equal(vm.preview.value, null, '更换文件必须清空旧预检')
vm.open(1)
vm.projectId.value = 2
await nextTick()
assert.equal(vm.file.value, null)
assert.equal(vm.preview.value, null)
assert.equal(vm.defaultRequirementId.value, null)
assert.deepEqual({ ...vm.overrides }, {})

for (const view of ['ProjectDetailView.vue', 'TestsView.vue']) {
  const page = await readFile(new URL(`../views/${view}`, import.meta.url), 'utf8')
  assert.match(page, /<TestCaseImportDialog/)
  assert.match(page, />导入用例<\/el-button>/)
}
console.log('test case import precheck invalidation, project isolation and commit behavior passed')
