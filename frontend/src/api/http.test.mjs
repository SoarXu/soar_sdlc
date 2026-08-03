import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./http.js', import.meta.url), 'utf8')

assert.match(source, /http\.interceptors\.response\.use/)
assert.match(source, /error\?\.response\?\.status === 401/)
assert.match(source, /handleSessionExpired\(error\?\.config\?\.url\)/)
assert.match(source, /const sessionExpired = await handleSessionExpired/)
assert.match(source, /if \(sessionExpired\) error\.sessionExpired = true/)
assert.match(source, /return Promise\.reject\(error\)/)
assert.match(source, /ElMessage\.warning\(\{[\s\S]*?onClose: resolve/)
assert.match(source, /router\.resolve\(location\)\.href/)
assert.match(source, /window\.location\.replace\(/)
assert.doesNotMatch(source, /navigate: \(location\) => router\.replace\(location\)/)

console.log('http interceptor tests passed')
