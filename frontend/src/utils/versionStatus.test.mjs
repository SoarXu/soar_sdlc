import assert from 'node:assert/strict'
import { releaseStatus } from './versionStatus.js'

assert.equal(releaseStatus('1.0.0', { app_version: '1.0.0' }), '一致')
assert.equal(releaseStatus('1.0.0', { app_version: '1.0.1' }), '版本不一致')
assert.equal(releaseStatus('1.0.0', { app_version: '1.0.0', git_commit: 'different' }), '一致')
assert.equal(releaseStatus('1.0.0', null), '版本信息无法获取')

console.log('version status tests passed')
