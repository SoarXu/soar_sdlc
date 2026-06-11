<template>
  <section>
    <div class="page-head">
      <div>
        <h1>迭代</h1>
        <p>维护迭代计划、周期、负责人和目标，关联项目和负责人以名称选择。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增迭代</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="pagedIterations" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="迭代名称" min-width="180">
          <template #default="{ row }"><router-link class="table-link" :to="`/iterations/${row.id}`">{{ row.name }}</router-link></template>
        </el-table-column>
        <el-table-column label="项目" min-width="240"><template #default="{ row }">{{ (row.project_ids || []).map(id => labelById(projects, id)).join('、') }}</template></el-table-column>
        <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="130" />
        <el-table-column prop="end_date" label="结束日期" width="130" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该迭代？" @confirm="removeIteration(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-pagination">
        <el-pagination
          v-model:current-page="iterationPage"
          v-model:page-size="iterationPageSize"
          :page-sizes="iterationPageSizes"
          :total="iterationTotal"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑迭代' : '新增迭代'" width="560px">
      <el-form label-position="top">
        <el-form-item label="迭代名称" required><el-input v-model="form.name" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" required>
            <el-select v-model="form.project_ids" multiple filterable placeholder="请选择项目（仅顶级项目）">
              <el-option v-for="project in topLevelProjects" :key="project.id" :label="project.name" :value="project.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="负责人">
            <el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
          <el-form-item label="结束日期"><el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
        </div>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="规划中" value="planning" />
            <el-option label="进行中" value="active" />
            <el-option label="已完成" value="finished" />
            <el-option label="已关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标"><el-input v-model="form.goal" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitIteration">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createIteration, deleteIteration, fetchIterations, updateIteration } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const iterations = ref([])
const projects = ref([])
const users = ref([])
const {
  page: iterationPage,
  pageSize: iterationPageSize,
  pageSizes: iterationPageSizes,
  total: iterationTotal,
  pagedItems: pagedIterations
} = usePagination(iterations)
const topLevelProjects = computed(() => projects.value.filter(p => !p.parent_id))
const form = reactive({ project_ids: [], name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' })

function resetForm() { Object.assign(form, { project_ids: [], name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' }) }
function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function openEdit(row) { editingId.value = row.id; Object.assign(form, { ...row, project_ids: row.project_ids || [], goal: row.goal || '' }); dialogVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [iterationRes, projectRes, userRes] = await Promise.all([fetchIterations(), fetchProjects(), fetchUsers()])
    iterations.value = iterationRes.data
    projects.value = projectRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('迭代列表加载失败')
  } finally {
    loading.value = false
  }
}

async function submitIteration() {
  if (!form.project_ids.length || !form.name.trim()) return ElMessage.warning('请选择项目并填写迭代名称')
  saving.value = true
  try {
    const payload = { ...form, owner_id: form.owner_id || null }
    if (editingId.value) await updateIteration(editingId.value, payload)
    else await createIteration(payload)
    dialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function removeIteration(id) { await deleteIteration(id); await loadData() }
onMounted(loadData)
</script>
