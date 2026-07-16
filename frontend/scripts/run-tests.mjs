import { readdir } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { pathToFileURL } from 'node:url'

async function findTests(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = await Promise.all(entries.map(async (entry) => {
    const filePath = path.join(directory, entry.name)
    return entry.isDirectory() ? findTests(filePath) : [filePath]
  }))
  return files.flat().filter((filePath) => filePath.endsWith('.test.mjs'))
}

const filters = process.argv.slice(2).map((value) => value.toLowerCase())
const frontendRoot = process.cwd()
const testFiles = await findTests(path.join(frontendRoot, 'src'))
const selectedFiles = testFiles.filter((filePath) => {
  if (!filters.length) return true
  const relativePath = path.relative(frontendRoot, filePath).toLowerCase()
  return filters.some((filter) => relativePath.includes(filter))
})

if (!selectedFiles.length) {
  throw new Error(`No test files matched: ${filters.join(', ')}`)
}

process.chdir(path.dirname(frontendRoot))

for (const filePath of selectedFiles.sort()) {
  await import(pathToFileURL(filePath).href)
}
