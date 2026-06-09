<template>
  <section>
    <div class="page-head">
      <div>
        <h1>测试管理</h1>
        <p>维护测试用例库和测试单，关联项目、需求、迭代、人员和用例均以名称展示。</p>
      </div>
      <div class="page-actions"><el-button @click="openRunCreate">新增测试单</el-button><el-button type="primary" @click="openCaseCreate">新增用例</el-button></div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="用例库" name="cases">
        <el-card shadow="never">
          <el-table v-loading="loading" :data="pagedTestCases" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="title" label="用例标题" min-width="220" />
            <el-table-column label="项目" width="170"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
            <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
            <el-table-column label="默认测试人" width="140"><template #default="{ row }">{{ userLabel(users, row.default_tester_id) }}</template></el-table-column>
            <el-table-column prop="priority" label="优先级" width="100" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }"><el-button link type="primary" @click="openCaseEdit(row)">编辑</el-button><el-popconfirm title="确认删除该用例？" @confirm="removeCase(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
            </el-table-column>
          </el-table>
          <div class="table-pagination">
            <el-pagination
              v-model:current-page="casePage"
              v-model:page-size="casePageSize"
              :page-sizes="casePageSizes"
              :total="caseTotal"
              layout="total, sizes, prev, pager, next, jumper"
            />
          </div>
        </el-card>
      </el-tab-pane>
      <el-tab-pane label="测试单" name="runs">
        <el-card shadow="never">
          <el-table v-loading="loading" :data="pagedTestRuns" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="测试单名称" min-width="220" />
            <el-table-column label="项目" width="170"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
            <el-table-column label="迭代" width="160"><template #default="{ row }">{{ labelById(iterations, row.iteration_id) }}</template></el-table-column>
            <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.test_owner_id) }}</template></el-table-column>
            <el-table-column prop="status" label="状态" width="110" />
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }"><el-button link type="primary" @click="openRunEdit(row)">编辑</el-button><el-button link type="success" @click="openSelectCases(row)">选用例</el-button><el-button link type="warning" @click="openExecution">记录结果</el-button><el-popconfirm title="确认删除该测试单？" @confirm="removeRun(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
            </el-table-column>
          </el-table>
          <div class="table-pagination">
            <el-pagination
              v-model:current-page="runPage"
              v-model:page-size="runPageSize"
              :page-sizes="runPageSizes"
              :total="runTotal"
              layout="total, sizes, prev, pager, next, jumper"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="caseDialogVisible" :title="editingCaseId ? '编辑用例' : '新增用例'" width="620px">
      <el-form label-position="top">
        <el-form-item label="用例标题" required><el-input v-model="caseForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目"><el-select v-model="caseForm.project_id" clearable filterable placeholder="请选择项目"><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="需求"><el-select v-model="caseForm.requirement_id" clearable filterable placeholder="请选择需求"><el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
          <el-form-item label="默认测试人"><el-select v-model="caseForm.default_tester_id" clearable filterable placeholder="请选择测试人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="类型"><el-input v-model="caseForm.case_type" /></el-form-item>
        </div>
        <div class="form-grid"><el-form-item label="优先级"><el-select v-model="caseForm.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item><el-form-item label="状态"><el-select v-model="caseForm.status"><el-option label="启用" value="active" /><el-option label="停用" value="inactive" /></el-select></el-form-item></div>
        <el-form-item label="前置条件"><el-input v-model="caseForm.precondition" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="预期结果"><el-input v-model="caseForm.expected_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="caseDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCase">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="runDialogVisible" :title="editingRunId ? '编辑测试单' : '新增测试单'" width="560px">
      <el-form label-position="top">
        <el-form-item label="测试单名称" required><el-input v-model="runForm.name" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" required><el-select v-model="runForm.project_id" filterable placeholder="请选择项目"><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="迭代"><el-select v-model="runForm.iteration_id" clearable filterable placeholder="请选择迭代"><el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item>
          <el-form-item label="测试负责人"><el-select v-model="runForm.test_owner_id" clearable filterable placeholder="请选择负责人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="状态"><el-select v-model="runForm.status"><el-option label="规划中" value="planning" /><el-option label="执行中" value="running" /><el-option label="完成" value="finished" /></el-select></el-form-item>
        </div>
        <el-form-item label="备注"><el-input v-model="runForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="runDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRun">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="selectDialogVisible" title="选择测试用例" width="520px">
      <el-form label-position="top">
        <el-form-item label="测试单"><el-input :model-value="labelById(testRuns, selectedRunId, 'name')" disabled /></el-form-item>
        <el-form-item label="测试用例" required><el-select v-model="selectForm.test_case_ids" multiple filterable placeholder="请选择测试用例"><el-option v-for="item in testCases" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="执行人"><el-select v-model="selectForm.tester_id" clearable filterable placeholder="请选择执行人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
      </el-form>
      <template #footer><el-button @click="selectDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitSelectCases">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="executionDialogVisible" title="记录执行结果" width="520px">
      <el-form label-position="top">
        <el-form-item label="测试单用例" required><el-select v-model="executionForm.run_case_id" filterable placeholder="请选择执行记录"><el-option v-for="item in testRunCases" :key="item.id" :label="runCaseLabel(item)" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="结果"><el-select v-model="executionForm.result"><el-option label="通过" value="passed" /><el-option label="失败" value="failed" /><el-option label="阻塞" value="blocked" /></el-select></el-form-item>
        <el-form-item label="备注"><el-input v-model="executionForm.remark" type="textarea" :rows="3" /></el-form-item>
        <el-form-item v-if="executionForm.result === 'failed'" label="失败后创建 Bug 标题"><el-input v-model="executionForm.bug_title" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="executionDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitExecution">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchIterations } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { createTestCase, deleteTestCase, fetchTestCases, updateTestCase } from '../api/testCases'
import { createBugFromTestRunCase, createTestRun, deleteTestRun, fetchTestRunCases, fetchTestRuns, selectTestCases, updateTestRun, updateTestRunCase } from '../api/testRuns'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'

const activeTab = ref('cases'), saving = ref(false), loading = ref(false)
const testCases = ref([]), testRuns = ref([]), testRunCases = ref([]), projects = ref([]), requirements = ref([]), iterations = ref([]), users = ref([])
const {
  page: casePage,
  pageSize: casePageSize,
  pageSizes: casePageSizes,
  total: caseTotal,
  pagedItems: pagedTestCases
} = usePagination(testCases)
const {
  page: runPage,
  pageSize: runPageSize,
  pageSizes: runPageSizes,
  total: runTotal,
  pagedItems: pagedTestRuns
} = usePagination(testRuns)
const caseDialogVisible = ref(false), runDialogVisible = ref(false), selectDialogVisible = ref(false), executionDialogVisible = ref(false)
const editingCaseId = ref(null), editingRunId = ref(null), selectedRunId = ref(null)
const caseForm = reactive({ project_id: null, requirement_id: null, title: '', case_type: '', priority: 'medium', default_tester_id: null, precondition: '', expected_result: '', status: 'active' })
const runForm = reactive({ project_id: null, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' })
const selectForm = reactive({ test_case_ids: [], tester_id: null })
const executionForm = reactive({ run_case_id: null, result: 'passed', remark: '', bug_title: '' })

function runCaseLabel(item) { return `${labelById(testRuns.value, item.test_run_id, 'name')} / ${labelById(testCases.value, item.test_case_id, 'title')} / ${item.result}` }
function openCaseCreate() { editingCaseId.value = null; Object.assign(caseForm, { project_id: null, requirement_id: null, title: '', case_type: '', priority: 'medium', default_tester_id: null, precondition: '', expected_result: '', status: 'active' }); caseDialogVisible.value = true }
function openCaseEdit(row) { editingCaseId.value = row.id; Object.assign(caseForm, { ...row, case_type: row.case_type || '', precondition: row.precondition || '', expected_result: row.expected_result || '' }); caseDialogVisible.value = true }
function openRunCreate() { editingRunId.value = null; Object.assign(runForm, { project_id: null, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' }); runDialogVisible.value = true }
function openRunEdit(row) { editingRunId.value = row.id; Object.assign(runForm, { ...row, remark: row.remark || '' }); runDialogVisible.value = true }
function openSelectCases(row) { selectedRunId.value = row.id; selectForm.test_case_ids = []; selectForm.tester_id = null; selectDialogVisible.value = true }
async function openExecution() { Object.assign(executionForm, { run_case_id: null, result: 'passed', remark: '', bug_title: '' }); await loadRunCases(); executionDialogVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [caseRes, runRes, runCaseRes, projectRes, reqRes, iterationRes, userRes] = await Promise.all([fetchTestCases(), fetchTestRuns(), fetchTestRunCases(), fetchProjects(), fetchRequirements(), fetchIterations(), fetchUsers()])
    testCases.value = caseRes.data; testRuns.value = runRes.data; testRunCases.value = runCaseRes.data; projects.value = projectRes.data; requirements.value = reqRes.data; iterations.value = iterationRes.data; users.value = userRes.data
  } catch { ElMessage.error('测试管理数据加载失败') } finally { loading.value = false }
}
async function loadRunCases() { testRunCases.value = (await fetchTestRunCases()).data }
async function submitCase() { if (!caseForm.title.trim()) return ElMessage.warning('请填写用例标题'); saving.value = true; try { const payload = { ...caseForm, project_id: caseForm.project_id || null, requirement_id: caseForm.requirement_id || null, default_tester_id: caseForm.default_tester_id || null }; if (editingCaseId.value) await updateTestCase(editingCaseId.value, payload); else await createTestCase(payload); caseDialogVisible.value = false; await loadData() } finally { saving.value = false } }
async function submitRun() { if (!runForm.project_id || !runForm.name.trim()) return ElMessage.warning('请选择项目并填写测试单名称'); saving.value = true; try { const payload = { ...runForm, iteration_id: runForm.iteration_id || null, test_owner_id: runForm.test_owner_id || null }; if (editingRunId.value) await updateTestRun(editingRunId.value, payload); else await createTestRun(payload); runDialogVisible.value = false; await loadData() } finally { saving.value = false } }
async function submitSelectCases() { if (!selectForm.test_case_ids.length) return ElMessage.warning('请选择测试用例'); saving.value = true; try { await selectTestCases(selectedRunId.value, { test_case_ids: selectForm.test_case_ids, tester_id: selectForm.tester_id || null }); selectDialogVisible.value = false; await loadData(); ElMessage.success('用例已加入测试单') } finally { saving.value = false } }
async function submitExecution() { if (!executionForm.run_case_id) return ElMessage.warning('请选择执行记录'); saving.value = true; try { await updateTestRunCase(executionForm.run_case_id, { result: executionForm.result, remark: executionForm.remark }); if (executionForm.result === 'failed' && executionForm.bug_title.trim()) await createBugFromTestRunCase(executionForm.run_case_id, { title: executionForm.bug_title, actual_result: executionForm.remark }); executionDialogVisible.value = false; await loadData(); ElMessage.success('执行结果已保存') } finally { saving.value = false } }
async function removeCase(id) { await deleteTestCase(id); await loadData() }
async function removeRun(id) { await deleteTestRun(id); await loadData() }
onMounted(loadData)
</script>
