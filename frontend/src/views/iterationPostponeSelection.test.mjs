import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const views = await Promise.all([
  readFile(new URL('./IterationDetailView.vue', import.meta.url), 'utf8'),
  readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')
])

for (const [name, source] of [['迭代详情', views[0]], ['项目详情', views[1]]]) {
  assert.match(source, /label="延期原因"/, `${name} 应明确说明延期原因的用途`)
  assert.match(source, /v-model="deferWorkItemsForm(?:\.value)?\.defer_reason"/, `${name} 应绑定延期原因字段`)
  assert.match(source, /<el-table[^>]*@selection-change="onDeferRequirementSelection"[\s\S]*?<el-table-column type="selection"/, `${name} 的需求应支持逐项勾选`)
  assert.match(source, /<el-table[^>]*@selection-change="onDeferTaskSelection"[\s\S]*?<el-table-column type="selection"/, `${name} 的任务应支持逐项勾选`)
  assert.match(source, /selectedDeferRequirementIds\.value\.length|selectedDeferRequirementIds\.length/, `${name} 应展示已选需求数量`)
  assert.match(source, /selectedDeferTaskIds\.value\.length|selectedDeferTaskIds\.length/, `${name} 应展示已选任务数量`)
  assert.match(source, /requirement_ids:\s*selectedDeferRequirementIds(?:\.value)?/, `${name} 只能提交选中的需求`)
  assert.match(source, /task_ids:\s*selectedDeferTaskIds(?:\.value)?/, `${name} 只能提交选中的任务`)
  assert.match(source, /defer_reason:\s*deferWorkItemsForm(?:\.value)?\.defer_reason/, `${name} 应提交延期原因`)
  assert.match(source, /\.defer-work-lists\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\);/, `${name} 的延期列表应上下排列`)
}

console.log('iteration postpone selection contract passed')
