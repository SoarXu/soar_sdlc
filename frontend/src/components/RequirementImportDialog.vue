<template>
  <el-dialog v-model="visible" title="导入需求 · 对比与确认" width="min(1180px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
    <div class="import-help">上传模板或导出的需求文件。带需求ID时按ID更新，否则按当前项目和标题匹配。<el-button link type="primary" :disabled="saving" @click="downloadTemplate">下载模板</el-button></div>
    <el-upload :key="uploadKey" :auto-upload="false" :limit="1" accept=".xlsx" :disabled="saving" :on-change="onFileChange" :on-remove="clearFile"><el-button :disabled="saving">选择 Excel 文件</el-button></el-upload>
    <el-radio-group v-model="strategy" :disabled="saving" class="import-strategy"><el-radio label="update_existing">更新已有需求</el-radio><el-radio label="create_duplicate">重复创建</el-radio></el-radio-group>
    <template v-if="preview">
      <p>有效 {{ preview.valid_count }} 行，失败 {{ preview.error_count }} 行，重复 {{ preview.duplicate_count }} 行，提出人待确认 {{ preview.unresolved_count }} 行</p>
      <el-alert v-if="!valid" title="选择已变化或提交失败，请重新预检后确认导入。" type="info" :closable="false" />
      <el-table v-if="preview.errors?.length" :data="preview.errors" border size="small"><el-table-column prop="row_number" label="行号" width="70" /><el-table-column label="错误"><template #default="{ row }">{{ row.messages.join('；') }}</template></el-table-column></el-table>
      <el-table :data="preview.rows" row-key="row_number" border size="small" max-height="480" class="preview-table">
        <el-table-column type="expand"><template #default="{ row }">
          <div class="row-comparison">
            <el-alert v-if="row.moves_linked_tasks && strategy === 'update_existing'" title="变更迭代时，关联任务也会移入新迭代。" type="warning" :closable="false" />
            <el-table v-if="row.changes.length" :data="row.changes" border size="small"><el-table-column prop="label" label="修改字段" width="110" /><el-table-column label="平台当前值"><template #default="{ row: change }"><pre>{{ change.old_value ?? '（空）' }}</pre></template></el-table-column><el-table-column label="导入后值"><template #default="{ row: change }"><pre class="changed-value">{{ change.new_value ?? '（空）' }}</pre></template></el-table-column></el-table>
            <p v-else>与平台内容一致，将跳过更新。</p>
          </div>
        </template></el-table-column>
        <el-table-column prop="row_number" label="行号" width="65" />
        <el-table-column prop="title" label="需求标题" min-width="170" show-overflow-tooltip />
        <el-table-column prop="existing_requirement_id" label="已有ID" width="90" />
        <el-table-column label="变更" width="115"><template #default="{ row }">{{ actionLabel(row) }}</template></el-table-column>
        <el-table-column label="提出人" min-width="320"><template #default="{ row }">
          <div class="proposer-state"><el-tag :type="statusType(row.proposer_status)" size="small">{{ statusLabel(row.proposer_status) }}</el-tag><span>{{ row.proposer_input || (row.proposer_status === 'preserved' ? '保留原提出人' : '未填写') }}</span></div>
          <RequirementImportProposerSelect :model-value="decisions[row.row_number]?.proposer_external_id || row.proposer?.external_id || ''" :candidates="row.proposer_candidates" :selected="row.proposer" :disabled="saving || !!decisions[row.row_number]?.skip" @update:model-value="setProposer(row.row_number, $event)" />
          <small v-if="row.proposer_message">{{ row.proposer_message }}</small>
        </template></el-table-column>
        <el-table-column label="跳过" width="70"><template #default="{ row }"><el-checkbox :model-value="!!decisions[row.row_number]?.skip" :disabled="saving" @update:model-value="setSkipped(row.row_number, $event)" /></template></el-table-column>
      </el-table>
      <p class="import-footnote">展开行查看变更。空提出人更新时保留原值；空描述、类型或验收标准会清空对应字段。工作流状态、评审状态和当前处理人保持原值。</p>
    </template>
    <template #footer><el-button :disabled="saving" @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="runPreview">预检</el-button><el-button type="success" :disabled="!ready" :loading="saving" @click="commit">确认导入</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { previewRequirementImport, commitRequirementImport, downloadRequirementImportTemplate } from '../api/requirements'
import { showActionError } from '../utils/actionFeedback'
import RequirementImportProposerSelect from './RequirementImportProposerSelect.vue'

const emit = defineEmits(['completed'])
const visible = ref(false)
const projectId = ref(null)
const file = ref(null)
const preview = ref(null)
const strategy = ref('update_existing')
const decisions = reactive({})
const saving = ref(false)
const valid = ref(false)
const uploadKey = ref(0)
const ready = computed(() => valid.value && !saving.value && !!preview.value?.preview_token && !preview.value.error_count && !preview.value.unresolved_count && !!preview.value.rows?.length)
let revision = 0
function invalidate() { revision++; valid.value = false }
watch(strategy, invalidate, { flush: 'sync' })
function open(id) {
  invalidate(); projectId.value = id; file.value = null; preview.value = null
  strategy.value = 'update_existing'
  for (const key of Object.keys(decisions)) delete decisions[key]
  uploadKey.value++; visible.value = true
}
function onFileChange(upload) {
  invalidate(); file.value = upload.raw; preview.value = null
  for (const key of Object.keys(decisions)) delete decisions[key]
}
function clearFile() { onFileChange({ raw: null }) }
function setProposer(row, externalId) { decisions[row] = { ...decisions[row], proposer_external_id: externalId || null }; invalidate() }
function setSkipped(row, skip) { decisions[row] = { ...decisions[row], skip }; invalidate() }
function selectedDecisions() { return Object.entries(decisions).map(([row, value]) => ({ row_number: Number(row), ...value })).sort((a, b) => a.row_number - b.row_number) }
async function runPreview() {
  if (!file.value || saving.value) return ElMessage.warning('请选择 Excel 文件')
  valid.value = false; saving.value = true
  const requestRevision = revision
  try {
    const { data } = await previewRequirementImport(file.value, projectId.value, strategy.value, selectedDecisions())
    if (requestRevision === revision) { preview.value = data; valid.value = true }
  } catch (error) { showActionError(error, '导入预检失败') }
  finally { saving.value = false }
}
async function commit() {
  if (!ready.value) return ElMessage.warning('请先预检并处理待确认的提出人')
  saving.value = true
  try {
    const { data } = await commitRequirementImport(file.value, strategy.value, projectId.value, preview.value.preview_token, selectedDecisions())
    if (data.error_count) {
      preview.value = { ...preview.value, error_count: data.error_count, errors: data.errors }
      valid.value = false
      return
    }
    visible.value = false
    ElMessage.success(`导入完成，新增 ${data.created_count} 条，更新 ${data.updated_count} 条，跳过 ${data.skipped_count || 0} 条`)
    emit('completed')
  } catch (error) { valid.value = false; showActionError(error, '导入失败，请重新预检') }
  finally { saving.value = false }
}
async function downloadTemplate() {
  try {
    const { data } = await downloadRequirementImportTemplate(projectId.value)
    const url = URL.createObjectURL(data), link = document.createElement('a')
    link.href = url; link.download = '需求导入模板.xlsx'; link.click(); URL.revokeObjectURL(url)
  } catch (error) { showActionError(error, '模板下载失败') }
}
function actionLabel(row) { return ({ skip: '跳过', create: '新增', update: `${row.changes.length} 项变更`, unchanged: '无变化 · 跳过' })[row.action] }
function statusLabel(status) { return ({ skipped: '已跳过', empty: '可留空', preserved: '保留原值', matched: 'AD 已匹配', selected: '已选择', ambiguous: '重名待确认', unmatched: '未匹配', unavailable: 'AD 不可用' })[status] }
function statusType(status) { return ['matched', 'selected'].includes(status) ? 'success' : ['ambiguous', 'unmatched', 'unavailable'].includes(status) ? 'warning' : 'info' }
defineExpose({ open })
</script>

<style scoped>
.import-help { background: var(--el-fill-color-light); padding: 12px; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.import-strategy { margin-top: 16px; }
.preview-table { margin-top: 12px; }
.row-comparison { padding: 12px 30px; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 240px; overflow: auto; margin: 0; font: inherit; }
.changed-value { color: var(--el-color-primary); }
.proposer-state { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
small, .import-footnote { color: var(--el-text-color-secondary); }
.import-footnote { font-size: 12px; }
</style>
