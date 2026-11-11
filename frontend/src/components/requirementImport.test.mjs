import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, reactive, ref, watch, nextTick } from 'vue'

const source = await readFile(new URL('./RequirementImportDialog.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
const calls = [], events = []
let result = { rows: [{ row_number: 2 }], error_count: 0, unresolved_count: 1, preview_token: 'snapshot', errors: [] }
let failure = false
let finish
const vm = new Function('computed', 'reactive', 'ref', 'watch', 'ElMessage', 'showActionError', 'previewRequirementImport', 'commitRequirementImport', 'downloadRequirementImportTemplate', 'defineProps', 'defineEmits', 'defineExpose', `${script}\nreturn { open, onFileChange, runPreview, commit, preview, ready, decisions, strategy, visible, setProposer, setSkipped, projectId, downloadTemplate }`)(
  computed, reactive, ref, watch, { warning() {}, success() {} }, () => {},
  async (...args) => { calls.push(['preview', ...args]); return { data: await new Promise(resolve => { finish = () => resolve(result) }) } },
  async (...args) => { calls.push(['commit', ...args]); if (failure) throw new Error('conflict'); return { data: { created_count: 0, updated_count: 1, skipped_count: 0, error_count: 0 } } },
  () => {}, () => ({}), () => (...args) => events.push(args), () => {})

vm.open(7); vm.onFileChange({ raw: { name: 'requirements.xlsx' } }); await nextTick()
await vm.commit(); assert.equal(calls.length, 0, 'must precheck before writing')
let pending = vm.runPreview(); finish(); await pending
assert.equal(vm.ready.value, false, 'unresolved AD proposer blocks commit')
vm.setProposer(2, 'ad-123'); await nextTick()
result = { ...result, unresolved_count: 0 }
pending = vm.runPreview(); finish(); await pending
assert.equal(vm.ready.value, true)
vm.strategy.value = 'create_duplicate'; await nextTick(); assert.equal(vm.ready.value, false)
pending = vm.runPreview(); finish(); await pending
vm.setSkipped(2, true); await nextTick(); assert.equal(vm.ready.value, false)
pending = vm.runPreview(); finish(); await pending
failure = true; await vm.commit()
assert.equal(vm.visible.value, true, 'commit failure keeps dialog open')
assert.equal(vm.ready.value, false, 'failed commit requires a fresh preview')
failure = false
pending = vm.runPreview(); finish(); await pending
await vm.commit()
assert.equal(events[0][0], 'completed'); assert.equal(vm.visible.value, false)
assert.equal(calls.filter(c => c[0] === 'commit').at(-1)[4], 'snapshot')

vm.open(7); vm.onFileChange({ raw: { name: 'old.xlsx' } }); await nextTick()
pending = vm.runPreview()
vm.onFileChange({ raw: { name: 'new.xlsx' } }); await nextTick()
finish(); await pending
assert.equal(vm.preview.value, null, 'stale response must not replace the new file preview')
assert.equal(vm.ready.value, false)
console.log('requirement import preview, AD resolution, invalidation and failure behavior passed')

const apiSource = (await readFile(new URL('../api/requirements.js', import.meta.url), 'utf8')).replace(/^import .*$/gm, '').replace(/^export /gm, '')
const exportError = { response: { data: new Blob([JSON.stringify({ detail: { message: '需求 12 的需求描述超过 Excel 上限' } })]) } }
const exportApi = new Function('http', `${apiSource}\nreturn exportRequirements` )({ get: async () => { throw exportError } })
await assert.rejects(exportApi(7), error => error.apiMessage === '需求 12 的需求描述超过 Excel 上限')
console.log('requirement export preserves blob error messages')
