import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./WorkflowActionButtons.vue', import.meta.url), 'utf8')

assert.match(source, /actionNeedsConfirmation/)
assert.match(source, /workflowConfirmationMessage/)

const submitBlock = source.slice(
  source.indexOf('async function submitActiveAction'),
  source.indexOf('async function submitAction')
)

assert.doesNotMatch(submitBlock, /ElMessageBox\.confirm/)
assert.doesNotMatch(source, /ui_config\?\.confirm_message/)
assert.doesNotMatch(source, /ui_config\?\.confirm_title/)
assert.match(source, /recommended_owner_id/)
assert.match(source, /resolved_default_owner_id/)
assert.match(source, /original_owner_unavailable_reason/)
assert.match(source, /originalOwnerUnavailableMessage/)
assert.match(source, /reactivationAllowsUnassigned/)
assert.match(source, /reactivationRequiresOwner/)
assert.match(source, /missingRequiredOwner/)
assert.match(source, /submitDisabled/)
assert.match(source, /field\.readonly/)
assert.match(source, /noActiveTargetIteration/)
assert.match(source, /请先启动迭代/)
assert.match(source, /:disabled="submitDisabled"/)
assert.match(source, /原处理人仍有效，将默认保留/)
assert.match(source, /请选择处理人/)
assert.match(source, /可保持未分派/)
assert.match(source, /ITERATION_HAS_OPEN_ITEMS/)
assert.match(source, /blockerDetail/)
assert.match(source, /blockerTypeFilter/)
assert.match(source, /blockerRows/)
assert.match(source, /blockerDetailRoute\(row\)/)
assert.match(source, /存在未完成事项，无法结束迭代/)

console.log('workflow action button behavior tests passed')
