<template>
  <section>
    <div class="page-head">
      <div>
        <h1>测试管理</h1>
        <p>维护测试用例库和测试单，执行结果与失败提交 Bug 全部通过后端接口落库。</p>
      </div>
      <div class="page-actions">
        <el-button @click="openRunCreate">新增测试单</el-button>
        <el-button type="primary" @click="openCaseCreate">新增用例</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="用例库" name="cases">
        <el-card shadow="never">
          <el-table v-loading="loadingCases" :data="testCases" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="title" label="用例标题" min-width="220" />
            <el-table-column prop="project_id" label="项目 ID" width="110" />
            <el-table-column prop="requirement_id" label="需求 ID" width="110" />
            <el-table-column prop="case_type" label="类型" width="120" />
            <el-table-column prop="priority" label="优先级" width="100" />
            <el-table-column prop="default_tester_id" label="默认测试人" width="120" />
            <el-table-column prop="status" label="状态" width="110" />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openCaseEdit(row)">编辑</el-button>
                <el-popconfirm title="确认删除该用例？" @confirm="removeCase(row.id)">
                  <template #reference><el-button link type="danger">删除</el-button></template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="测试单" name="runs">
        <el-card shadow="never">
          <el-table v-loading="loadingRuns" :data="testRuns" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="测试单名称" min-width="220" />
            <el-table-column prop="project_id" label="项目 ID" width="110" />
            <el-table-column prop="iteration_id" label="迭代 ID" width="110" />
            <el-table-column prop="test_owner_id" label="测试负责人" width="120" />
            <el-table-column prop="status" label="状态" width="110" />
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openRunEdit(row)">编辑</el-button>
                <el-button link type="success" @click="openSelectCases(row)">选用例</el-button>
                <el-button link type="warning" @click="openExecution(row)">记录结果</el-button>
                <el-popconfirm title="确认删除该测试单？" @confirm="removeRun(row.id)">
                  <template #reference><el-button link type="danger">删除</el-button></template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="caseDialogVisible" :title="editingCaseId ? '编辑用例' : '新增用例'" width="620px">
      <el-form label-position="top">
        <el-form-item label="用例标题" required><el-input v-model="caseForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目 ID"><el-input-number v-model="caseForm.project_id" :min="1" /></el-form-item>
          <el-form-item label="需求 ID"><el-input-number v-model="caseForm.requirement_id" :min="1" /></el-form-item>
          <el-form-item label="默认测试人 ID"><el-input-number v-model="caseForm.default_tester_id" :min="1" /></el-form-item>
          <el-form-item label="类型"><el-input v-model="caseForm.case_type" /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="优先级">
            <el-select v-model="caseForm.priority">
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="caseForm.status">
              <el-option label="启用" value="active" />
              <el-option label="停用" value="inactive" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="前置条件"><el-input v-model="caseForm.precondition" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="预期结果"><el-input v-model="caseForm.expected_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="caseDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCase">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="runDialogVisible" :title="editingRunId ? '编辑测试单' : '新增测试单'" width="560px">
      <el-form label-position="top">
        <el-form-item label="测试单名称" required><el-input v-model="runForm.name" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目 ID" required><el-input-number v-model="runForm.project_id" :min="1" /></el-form-item>
          <el-form-item label="迭代 ID"><el-input-number v-model="runForm.iteration_id" :min="1" /></el-form-item>
          <el-form-item label="测试负责人 ID"><el-input-number v-model="runForm.test_owner_id" :min="1" /></el-form-item>
          <el-form-item label="状态">
            <el-select v-model="runForm.status">
              <el-option label="规划中" value="planning" />
              <el-option label="执行中" value="running" />
              <el-option label="完成" value="finished" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="备注"><el-input v-model="runForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="runDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitRun">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="selectDialogVisible" title="选择测试用例" width="520px">
      <el-form label-position="top">
        <el-form-item label="测试单 ID"><el-input :model-value="selectedRunId" disabled /></el-form-item>
        <el-form-item label="用例 ID，多个用英文逗号分隔" required><el-input v-model="selectForm.test_case_ids" /></el-form-item>
        <el-form-item label="执行人 ID"><el-input-number v-model="selectForm.tester_id" :min="1" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="selectDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitSelectCases">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="executionDialogVisible" title="记录执行结果" width="520px">
      <el-form label-position="top">
        <el-form-item label="测试单用例执行 ID" required><el-input-number v-model="executionForm.run_case_id" :min="1" /></el-form-item>
        <el-form-item label="结果">
          <el-select v-model="executionForm.result">
            <el-option label="通过" value="passed" />
            <el-option label="失败" value="failed" />
            <el-option label="阻塞" value="blocked" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="executionForm.remark" type="textarea" :rows="3" /></el-form-item>
        <el-form-item v-if="executionForm.result === 'failed'" label="失败后创建 Bug 标题">
          <el-input v-model="executionForm.bug_title" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="executionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitExecution">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createTestCase, deleteTestCase, fetchTestCases, updateTestCase } from '../api/testCases'
import { createBugFromTestRunCase, createTestRun, deleteTestRun, fetchTestRuns, selectTestCases, updateTestRun, updateTestRunCase } from '../api/testRuns'

const activeTab = ref('cases')
const saving = ref(false)
const loadingCases = ref(false)
const loadingRuns = ref(false)
const testCases = ref([])
const testRuns = ref([])
const caseDialogVisible = ref(false)
const runDialogVisible = ref(false)
const selectDialogVisible = ref(false)
const executionDialogVisible = ref(false)
const editingCaseId = ref(null)
const editingRunId = ref(null)
const selectedRunId = ref(null)
const caseForm = reactive({ project_id: null, requirement_id: null, title: '', case_type: '', priority: 'medium', default_tester_id: null, precondition: '', expected_result: '', status: 'active' })
const runForm = reactive({ project_id: null, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' })
const selectForm = reactive({ test_case_ids: '', tester_id: null })
const executionForm = reactive({ run_case_id: null, result: 'passed', remark: '', bug_title: '' })

function openCaseCreate() { editingCaseId.value = null; Object.assign(caseForm, { project_id: null, requirement_id: null, title: '', case_type: '', priority: 'medium', default_tester_id: null, precondition: '', expected_result: '', status: 'active' }); caseDialogVisible.value = true }
function openCaseEdit(row) { editingCaseId.value = row.id; Object.assign(caseForm, { ...row, case_type: row.case_type || '', precondition: row.precondition || '', expected_result: row.expected_result || '' }); caseDialogVisible.value = true }
function openRunCreate() { editingRunId.value = null; Object.assign(runForm, { project_id: null, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' }); runDialogVisible.value = true }
function openRunEdit(row) { editingRunId.value = row.id; Object.assign(runForm, { ...row, remark: row.remark || '' }); runDialogVisible.value = true }
function openSelectCases(row) { selectedRunId.value = row.id; selectForm.test_case_ids = ''; selectForm.tester_id = null; selectDialogVisible.value = true }
function openExecution() { Object.assign(executionForm, { run_case_id: null, result: 'passed', remark: '', bug_title: '' }); executionDialogVisible.value = true }

async function loadCases() { loadingCases.value = true; try { testCases.value = (await fetchTestCases()).data } finally { loadingCases.value = false } }
async function loadRuns() { loadingRuns.value = true; try { testRuns.value = (await fetchTestRuns()).data } finally { loadingRuns.value = false } }

async function submitCase() {
  if (!caseForm.title.trim()) return ElMessage.warning('请填写用例标题')
  saving.value = true
  try {
    const payload = { ...caseForm, project_id: caseForm.project_id || null, requirement_id: caseForm.requirement_id || null, default_tester_id: caseForm.default_tester_id || null }
    if (editingCaseId.value) await updateTestCase(editingCaseId.value, payload)
    else await createTestCase(payload)
    caseDialogVisible.value = false
    await loadCases()
  } finally { saving.value = false }
}

async function submitRun() {
  if (!runForm.project_id || !runForm.name.trim()) return ElMessage.warning('请填写项目 ID 和测试单名称')
  saving.value = true
  try {
    const payload = { ...runForm, iteration_id: runForm.iteration_id || null, test_owner_id: runForm.test_owner_id || null }
    if (editingRunId.value) await updateTestRun(editingRunId.value, payload)
    else await createTestRun(payload)
    runDialogVisible.value = false
    await loadRuns()
  } finally { saving.value = false }
}

async function submitSelectCases() {
  const ids = selectForm.test_case_ids.split(',').map((item) => Number(item.trim())).filter(Boolean)
  if (!ids.length) return ElMessage.warning('请填写用例 ID')
  saving.value = true
  try {
    await selectTestCases(selectedRunId.value, { test_case_ids: ids, tester_id: selectForm.tester_id || null })
    selectDialogVisible.value = false
    ElMessage.success('用例已加入测试单')
  } finally { saving.value = false }
}

async function submitExecution() {
  if (!executionForm.run_case_id) return ElMessage.warning('请填写测试单用例执行 ID')
  saving.value = true
  try {
    await updateTestRunCase(executionForm.run_case_id, { result: executionForm.result, remark: executionForm.remark })
    if (executionForm.result === 'failed' && executionForm.bug_title.trim()) {
      await createBugFromTestRunCase(executionForm.run_case_id, { title: executionForm.bug_title, actual_result: executionForm.remark })
      ElMessage.success('执行结果已保存并创建 Bug')
    } else {
      ElMessage.success('执行结果已保存')
    }
    executionDialogVisible.value = false
  } finally { saving.value = false }
}

async function removeCase(id) { await deleteTestCase(id); await loadCases() }
async function removeRun(id) { await deleteTestRun(id); await loadRuns() }

onMounted(async () => {
  await Promise.all([loadCases(), loadRuns()])
})
</script>
