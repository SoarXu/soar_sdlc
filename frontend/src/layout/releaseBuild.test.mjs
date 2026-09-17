import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const root = new URL('../../../', import.meta.url)
const version = (await readFile(new URL('VERSION', root), 'utf8')).trim()
const compose = await readFile(new URL('deployment/docker-compose.yml', root), 'utf8')
const backendDockerfile = await readFile(new URL('deployment/backend/Dockerfile', root), 'utf8')
const frontendDockerfile = await readFile(new URL('deployment/frontend/Dockerfile', root), 'utf8')
const script = await readFile(new URL('scripts/build_release_package.ps1', root), 'utf8')

assert.equal(version, '1.0.0')
assert.match(compose, /APP_VERSION:.*APP_VERSION/)
assert.match(compose, /COMPOSE_PROJECT_NAME:\?[^}]+/)
assert.match(compose, /GIT_COMMIT:.*GIT_COMMIT/)
assert.match(backendDockerfile, /ARG APP_VERSION/)
assert.match(backendDockerfile, /ARG GIT_COMMIT/)
assert.match(frontendDockerfile, /VITE_RELEASE_BUILD=1/)
assert.match(frontendDockerfile, /COPY frontend\/public/)
assert.match(script, /frontend\/public/)
assert.match(script, /git -C \$root archive/)
assert.match(script, /release\.env/)
assert.match(script, /VERSION/)

console.log('release build contracts passed')
