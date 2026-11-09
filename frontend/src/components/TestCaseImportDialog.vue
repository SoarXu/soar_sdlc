<template>
  <el-dialog v-model="visible" title="导入测试用例" width="960px" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
    <el-form label-position="top" :disabled="busy">
      <div class="import-context">
        <el-form-item label="目标项目" required>
          <el-select v-model="projectId" filterable placeholder="请选择项目" :disabled="lockProject">
            <el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认关联需求（用于 Excel 中关联需求留空的用例）">
          <el-select v-model="defaultRequirementId" clearable filterable placeholder="不选则留空的用例不关联需求" :disabled="!projectId">
            <el-option v-for="item in projectRequirements" :key="item.id" :label="requirementLabel(item)" :value="item.id" />
          </el-select>
        </el-form-item>
      </div>
      <div class="import-actions">
        <el-button :disabled="!projectId" @click="downloadTemplate">下载 Excel 模板</el-button>
        <el-upload ref="uploadRef" :auto-upload="false" :limit="1" accept=".xlsx" :disabled="busy || !projectId" :on-change="onFileChange" :on-remove="clearFile" :on-exceed="() => ElMessage.warning('请先移除原文件，再选择新文件')">
          <el-button :disabled="!projectId">选择 Excel 文件</el-button>
        </el-upload>
      </div>
      <p class="import-help">一行一条用例，最多 1000 条、10MB。关联需求可在模板中下拉选择，自动携带 ID；也可手填标题。支持文字换行，图片请在导入后补充。</p>
      <el-form-item label="重复处理（同项目、同需求、相同标题）">
        <el-radio-group v-model="duplicateStrategy">
          <el-radio value="skip">跳过重复</el-radio>
          <el-radio value="create_duplicate">仍然新增</el-radio>
        </el-radio-group>
      </el-form-item>
    </el-form>
    <template v-if="preview">
      <el-alert :type="preview.error_count ? 'warning' : 'success'" :closable="false" :title="`共 ${preview.total_count} 条，有效 ${preview.valid_count} 条，错误 ${preview.error_count} 条，疑似重复 ${preview.duplicate_count} 条`" />
      <template v-if="preview.requirement_groups.length">
        <p>需求关联：同一个名称只需指定一次。更改后请重新预检。</p>
        <el-table :data="preview.requirement_groups" border max-height="280">
          <el-table-column prop="reference" label="Excel 中的关联需求" min-width="200" show-overflow-tooltip />
          <el-table-column prop="count" label="用例数" width="80" />
          <el-table-column prop="message" label="匹配结果" min-width="180" />
          <el-table-column label="指定关联需求" min-width="300">
            <template #default="{ row }">
              <el-select :model-value="associationValue(row)" filterable :disabled="busy" placeholder="选择需求或暂不关联" @change="value => setAssociation(row.reference, value)">
                <el-option label="暂不关联需求" :value="0" />
                <el-option v-for="item in projectRequirements" :key="item.id" :label="requirementLabel(item)" :value="item.id" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-table v-if="preview.errors.length" :data="preview.errors" border max-height="220" class="import-results">
        <el-table-column prop="row_number" label="Excel 行号" width="110" />
        <el-table-column label="错误原因"><template #default="{ row }">{{ row.messages.join('；') }}</template></el-table-column>
      </el-table>
      <p>用例预览（最多展示前 100 条）</p>
      <el-table :data="preview.rows.slice(0, 100)" border max-height="220">
        <el-table-column prop="row_number" label="行号" width="80" />
        <el-table-column prop="title" label="用例标题" min-width="200" />
        <el-table-column label="关联需求" min-width="200"><template #default="{ row }">{{ row.requirement_id ? requirementLabel(projectRequirements.find(item => item.id === row.requirement_id) || { id: row.requirement_id, title: '需求' }) : '未关联' }}</template></el-table-column>
        <el-table-column label="处理" width="130"><template #default="{ row }">{{ row.messages.length ? '需修正' : row.duplicate && duplicateStrategy === 'skip' ? '跳过重复' : '新增' }}</template></el-table-column>
      </el-table>
      <p v-if="!ready && !preview.error_count" class="import-help">导入设置已变更，请重新预检。</p>
    </template>
    <template #footer>
      <el-button :disabled="busy" @click="visible = false">取消</el-button>
      <el-button :loading="busy" :disabled="busy || !projectId || !file" @click="runPreview">预检</el-button>
      <el-button type="primary" :loading="busy" :disabled="busy || !ready" @click="commit">确认导入</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadTestCaseImportTemplate, previewTestCaseImport, commitTestCaseImport } from '../api/testCases'
import { showActionError } from '../utils/actionFeedback'

const props = defineProps({
  projects: { type: Array, default: () => [] },
  requirements: { type: Array, default: () => [] },
  iterations: { type: Array, default: () => [] },
  lockProject: { type: Boolean, default: false }
})
const emit = defineEmits(['completed'])
const visible = ref(false), busy = ref(false), projectId = ref(null), defaultRequirementId = ref(null)
const file = ref(null), uploadRef = ref(null), preview = ref(null), checkedSignature = ref(null)
const duplicateStrategy = ref('skip'), overrides = reactive({})
const projectRequirements = computed(() => props.requirements.filter(item => item.project_id === projectId.value))
const signature = computed(() => JSON.stringify([projectId.value, defaultRequirementId.value, duplicateStrategy.value, overrides]))
const ready = computed(() => Boolean(file.value && preview.value && !preview.value.error_count && checkedSignature.value === signature.value))

function clearOverrides() { for (const key of Object.keys(overrides)) delete overrides[key] }
function clearFile() { file.value = null; preview.value = null; checkedSignature.value = null; clearOverrides() }
watch(projectId, () => {
  defaultRequirementId.value = null
  clearFile()
  uploadRef.value?.clearFiles()
}, { flush: 'sync' })

function open(selectedProjectId = null, requirementId = null) {
  if (busy.value) return
  projectId.value = selectedProjectId
  defaultRequirementId.value = requirementId
  clearFile()
  uploadRef.value?.clearFiles()
  duplicateStrategy.value = 'skip'
  visible.value = true
}
function onFileChange(upload) {
  clearFile()
  const selected = upload.raw
  if (!selected || !selected.name.toLowerCase().endsWith('.xlsx') || selected.size > 10 * 1024 * 1024) {
    uploadRef.value?.clearFiles()
    return ElMessage.warning('请选择不超过10MB的.xlsx文件')
  }
  file.value = selected
}
function requirementLabel(item) {
  const iteration = props.iterations?.find(iteration => iteration.id === item.iteration_id)
  return `${item.title}【需求#${item.id}】${item.status_name ? ' · ' + item.status_name : ''}${iteration ? ' · ' + iteration.name : ''}`
}
function associationValue(row) {
  return Object.hasOwn(overrides, row.reference) ? overrides[row.reference] ?? 0 : row.requirement_id ?? undefined
}
function setAssociation(reference, value) { overrides[reference] = value === 0 ? null : value }
function options() { return { projectId: projectId.value, defaultRequirementId: defaultRequirementId.value, duplicateStrategy: duplicateStrategy.value, overrides: { ...overrides } } }
async function downloadTemplate() {
  if (!projectId.value || busy.value) return
  busy.value = true
  try {
    const response = await downloadTestCaseImportTemplate(projectId.value)
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = '测试用例导入模板.xlsx'
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error) {
    // 下载接口的错误同样以 Blob 返回，解码后显示后端原因。
    if (error.response?.data instanceof Blob) {
      try { error.response.data = JSON.parse(await error.response.data.text()) } catch {}
    }
    showActionError(error, '模板下载失败')
  } finally { busy.value = false }
}
async function runPreview() {
  if (!projectId.value || !file.value || busy.value) return
  busy.value = true
  checkedSignature.value = null
  const requestSignature = signature.value
  try {
    const response = await previewTestCaseImport(file.value, options())
    preview.value = response.data
    checkedSignature.value = requestSignature
  } catch (error) { showActionError(error, '用例预检失败') }
  finally { busy.value = false }
}
async function commit() {
  if (!ready.value || busy.value) return
  busy.value = true
  try {
    const response = await commitTestCaseImport(file.value, options())
    visible.value = false
    clearFile()
    ElMessage.success(`已新增 ${response.data.created_count} 条用例，跳过 ${response.data.skipped_count} 条重复用例`)
    emit('completed')
  } catch (error) {
    checkedSignature.value = null
    showActionError(error, '用例导入失败，请重新预检')
  } finally { busy.value = false }
}
defineExpose({ open })
</script>

<style scoped>
.import-context { display: grid; grid-template-columns: 1fr 2fr; gap: 16px; }
.import-actions { display: flex; align-items: flex-start; flex-wrap: wrap; gap: 12px; }
.import-help { color: var(--el-text-color-secondary); line-height: 1.6; }
.import-results { margin-top: 12px; }
@media (max-width: 700px) { .import-context { grid-template-columns: 1fr; gap: 0; } }
</style>
