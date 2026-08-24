import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

async function readSource(fileName) {
  try {
    return await readFile(new URL(fileName, import.meta.url), 'utf8')
  } catch {
    return ''
  }
}

const composer = await readSource('./WorkItemCommentComposer.vue')

assert.notEqual(composer, '', 'the reusable work-item comment composer must exist')
assert.match(composer, /defineEmits\(\['submit'\]\)/)
assert.match(composer, /fetchWorkItemCommentMentionUsers/)
assert.match(composer, /mentionAudience/)
assert.match(composer, /loadMentionUsers/)
assert.match(composer, /v-model="draft\.body"/)
assert.match(composer, /mentionSuggestions/)
assert.match(composer, /selectMention\(user\)/)
assert.match(composer, /v-model="draft\.mentionedUserIds"/)
assert.match(
  composer,
  /emit\('submit', \{\s*body,\s*mentionedUserIds: \[\.\.\.draft\.mentionedUserIds\]\s*\}\)/,
  'the composer must emit both the comment body and all mentioned user IDs'
)

const panel = await readSource('./WorkItemCommentPanel.vue')

assert.match(panel, /import WorkItemCommentComposer from '\.\/WorkItemCommentComposer\.vue'/)
assert.match(panel, /<WorkItemCommentComposer[\s\S]*?@submit="submitComment"/)
assert.match(panel, /async function submitComment\(\{ body, mentionedUserIds \}\)/)
assert.match(panel, /mentioned_user_ids: mentionedUserIds/)
assert.match(panel, /commentComposer\.value\?\.clear\(\)/)

console.log('work item comment composer tests passed')
