import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const scriptPath = fileURLToPath(new URL('../../scripts/verify-fixed-desktop.mjs', import.meta.url))
const source = await readFile(scriptPath, 'utf8')

assert.match(source, /process\.env\.SOAR_VIEWPORT_WIDTH/)
assert.match(source, /process\.env\.SOAR_VIEWPORT_HEIGHT/)
assert.match(source, /1366x768/)
assert.match(source, /1440x900/)
assert.match(source, /1920x1080/)
assert.match(source, /['"]\/workflow['"]/)
assert.match(source, /verifyWorkflowDrawer/)
assert.match(source, /verifyWorkflowDrawerInteractions/)
assert.match(source, /verifyBugDictionaryRouting/)
assert.match(source, /interactionAcceptance/)
assert.match(source, /workflowDrawer/)
assert.equal((source.match(/Emulation\.setDeviceMetricsOverride/g) || []).length, 1)
assert.doesNotMatch(source, /__vueParentComponent/)
