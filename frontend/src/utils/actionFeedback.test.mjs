import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./actionFeedback.js', import.meta.url), 'utf8')

assert.match(source, /if \(error\?\.sessionExpired\) return Promise\.resolve\(\)/)

console.log('action feedback tests passed')
