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

console.log('workflow action button behavior tests passed')
