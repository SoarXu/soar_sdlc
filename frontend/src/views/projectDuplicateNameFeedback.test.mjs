import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const programsSource = await readFile(new URL('./ProgramsView.vue', import.meta.url), 'utf8')
const projectsSource = await readFile(new URL('./ProjectsView.vue', import.meta.url), 'utf8')

const submitProjectWithDuplicateFeedback = /async function submitProject\(\) \{[\s\S]*?\} catch \(error\) \{[\s\S]*?ElMessage\.error\(actionErrorMessage\(error, [\s\S]*?\)\)[\s\S]*?\} finally/

assert.match(programsSource, submitProjectWithDuplicateFeedback)
assert.match(projectsSource, submitProjectWithDuplicateFeedback)

console.log('project duplicate name feedback tests passed')
