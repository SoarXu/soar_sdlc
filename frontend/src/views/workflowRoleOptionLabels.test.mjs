import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const [workflowSource, projectSource] = await Promise.all([
  readFile(new URL('./WorkflowView.vue', import.meta.url), 'utf8'),
  readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')
])

assert.match(workflowSource, /\{ label: '开发主管', value: 'development_lead' \}/)
assert.match(workflowSource, /\{ label: '技术主管（兼容旧配置）', value: 'tech_lead' \}/)
assert.match(projectSource, /\{ label: '开发主管', value: 'development_lead' \}/)
assert.match(projectSource, /\{ label: '技术主管（兼容旧配置）', value: 'tech_lead' \}/)

console.log('workflow role option labels passed')
