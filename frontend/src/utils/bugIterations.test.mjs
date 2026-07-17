import assert from 'node:assert/strict'
import {
  bugIterationOptions,
  includeSelectedIterationOption,
  projectAncestorIds
} from './bugIterations.js'

function run(name, fn) {
  try {
    fn()
    console.log(`ok - ${name}`)
  } catch (error) {
    console.error(`not ok - ${name}`)
    throw error
  }
}

const projects = [
  { id: 1, name: 'Parent' },
  { id: 2, name: 'Child', parent_id: 1 },
  { id: 3, name: 'Sibling', parent_id: 1 }
]

const iterations = [
  { id: 10, name: 'Parent Active', state_category: 'normal', project_ids: [1] },
  { id: 11, name: 'Child Planning', state_category: 'start', project_ids: [2] },
  { id: 12, name: 'Parent Completed', state_category: 'terminal', project_ids: [1] },
  { id: 13, name: 'Sibling Active', state_category: 'normal', project_ids: [3] }
]

run('returns project ancestors including itself', () => {
  assert.deepEqual(projectAncestorIds(projects, 2), [2, 1])
})

run('bug iteration options include own and parent unfinished iterations', () => {
  assert.deepEqual(
    bugIterationOptions(iterations, projects, 2).map((item) => item.id),
    [10, 11]
  )
})

run('bug iteration options exclude completed and sibling iterations', () => {
  const optionIds = bugIterationOptions(iterations, projects, 2).map((item) => item.id)

  assert.equal(optionIds.includes(12), false)
  assert.equal(optionIds.includes(13), false)
})

run('selected iteration outside options is kept disabled so its name is displayed', () => {
  const options = bugIterationOptions(iterations, projects, 2)
  const displayOptions = includeSelectedIterationOption(options, iterations, 12)

  assert.equal(displayOptions.at(-1).id, 12)
  assert.equal(displayOptions.at(-1).name, 'Parent Completed')
  assert.equal(displayOptions.at(-1).disabled, true)
})
