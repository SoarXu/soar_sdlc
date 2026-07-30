import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProgramsView.vue', import.meta.url), 'utf8')

assert.match(source, /import \{ actionErrorMessage \} from '\.\.\/utils\/permissions'/,
  'program mutation failures must reuse the shared action error formatter')

function functionBlock(name, nextName) {
  const start = source.indexOf(`function ${name}`)
  const end = source.indexOf(nextName, start)
  assert.notEqual(start, -1, `missing ${name}`)
  assert.notEqual(end, -1, `missing boundary after ${name}`)
  return source.slice(start, end)
}

function asyncFunctionBlock(name, nextName) {
  const start = source.indexOf(`async function ${name}`)
  const end = source.indexOf(nextName, start)
  assert.notEqual(start, -1, `missing ${name}`)
  assert.notEqual(end, -1, `missing boundary after ${name}`)
  return source.slice(start, end)
}

const resetForm = functionBlock('resetForm', 'function openCreate')
assert.match(resetForm, /localStorage\.getItem\('current_user_id'\)/,
  'new program form must read the authenticated user ID')
assert.match(resetForm, /users\.value\.some\(\(user\) => user\.id === currentUserId\)/,
  'new program form must only preselect a current user returned by the user list')
assert.match(resetForm, /owner_id:\s*users\.value\.some\(\(user\) => user\.id === currentUserId\) \? currentUserId : null/,
  'new program form must preselect the authenticated user as owner')

const ownerFormItemStart = source.indexOf('<el-form-item label="负责人">')
const ownerFormItemEnd = source.indexOf('</el-form-item>', ownerFormItemStart)
assert.notEqual(ownerFormItemStart, -1, 'missing program owner field')
const ownerField = source.slice(ownerFormItemStart, ownerFormItemEnd)
assert.match(ownerField, /<el-select v-model="form\.owner_id"/,
  'program owner must be rendered as an editable selector')
assert.doesNotMatch(ownerField, /\bdisabled\b/,
  'program owner selector must remain editable for an owner transfer')

const openEdit = functionBlock('openEdit', 'function goToProject')
assert.match(openEdit, /owner_id:\s*row\.owner_id/,
  'editing a program must preserve the persisted owner instead of reapplying the current user')

const submitProgram = asyncFunctionBlock('submitProgram', 'async function changeProgramStatus')
assert.match(submitProgram, /catch \(error\) \{[\s\S]*?ElMessage\.error\(actionErrorMessage\(error, '项目集保存失败'\)\)[\s\S]*?await loadData\(\)/,
  'failed program creation or update must show an error and reload server state')

const changeProgramStatus = asyncFunctionBlock('changeProgramStatus', 'async function submitProject')
assert.match(changeProgramStatus, /catch \(error\) \{[\s\S]*?ElMessage\.error\(actionErrorMessage\(error, '项目集状态更新失败'\)\)[\s\S]*?await loadData\(\)[\s\S]*?throw error/,
  'failed program status updates must show one shared error, reload server state, and preserve the rejection')
assert.equal((changeProgramStatus.match(/ElMessage\.error/g) || []).length, 1,
  'the program status handler must not emit a duplicate error message')

const removeProgram = asyncFunctionBlock('removeProgram', 'onMounted(loadData)')
assert.match(removeProgram, /catch \(error\) \{[\s\S]*?ElMessage\.error\(actionErrorMessage\(error, '项目集删除失败'\)\)[\s\S]*?await loadData\(\)/,
  'failed program deletion must show an error and reload server state')

console.log('program owner permission UI contract passed')
