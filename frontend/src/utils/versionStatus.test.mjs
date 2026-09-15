import assert from 'node:assert/strict'
import { releaseStatus } from './versionStatus.js'

assert.equal(releaseStatus({ version: '1.0.0', commit: '' }, { app_version: '1.0.0', git_commit: null }), '一致')
assert.equal(releaseStatus({ version: '1.0.0', commit: '' }, { app_version: '1.0.1', git_commit: null }), '版本不一致')
assert.equal(releaseStatus({ version: '1.0.0', commit: 'aaa' }, { app_version: '1.0.0', git_commit: 'bbb' }), '构建不一致')
assert.equal(releaseStatus({ version: '1.0.0', commit: '' }, { app_version: '1.0.0', git_commit: 'aaa' }), '构建未确认')
assert.equal(releaseStatus({ version: '1.0.0', commit: '' }, null), '后端不可用')

console.log('version status tests passed')
