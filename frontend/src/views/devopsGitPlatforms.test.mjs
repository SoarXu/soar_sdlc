import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const viewSource = await readFile(new URL('./DevopsView.vue', import.meta.url), 'utf8')
const apiSource = await readFile(new URL('../api/devops.js', import.meta.url), 'utf8')

test('DevOps places Git platform management before repository and review workflows', () => {
  const platformsTab = viewSource.indexOf('label="Git 平台" name="platforms"')
  const commitsTab = viewSource.indexOf('name="commits"')

  assert.ok(platformsTab >= 0)
  assert.ok(platformsTab < commitsTab)
  assert.match(viewSource, /@click="openGitPlatformDialog"/)
  assert.match(viewSource, /@click="testGitPlatform\(row\)"/)
  assert.match(viewSource, /@click="editGitPlatform\(row\)"/)
  assert.match(viewSource, /@click="removeGitPlatform\(row\)"/)
})

test('Git platform edit form does not receive a token from persisted data', () => {
  assert.match(viewSource, /Object\.assign\(gitPlatformForm, \{[\s\S]*access_token: ''[\s\S]*\}\)/)
  assert.match(viewSource, /if \(editingGitPlatformId\.value && !payload\.access_token\) delete payload\.access_token/)
})

test('Git platform client exposes lifecycle and test-connection requests', () => {
  assert.match(apiSource, /http\.get\('\/devops\/git-platforms'\)/)
  assert.match(apiSource, /http\.post\('\/devops\/git-platforms', data\)/)
  assert.match(apiSource, /http\.put\(`\/devops\/git-platforms\/\$\{id\}`, data\)/)
  assert.match(apiSource, /http\.delete\(`\/devops\/git-platforms\/\$\{id\}`\)/)
  assert.match(apiSource, /http\.post\(`\/devops\/git-platforms\/\$\{id\}\/test`\)/)
})
