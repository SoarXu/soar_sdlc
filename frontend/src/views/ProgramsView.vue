<template>
  <section>
    <div class="page-head">
      <div>
        <h1>项目集</h1>
        <p>项目集以树状结构展示；展开项目集可查看子项目集和已绑定项目。</p>
      </div>
      <el-button type="primary" @click="openCreate()">新增项目集</el-button>
    </div>

    <el-card shadow="never">
      <el-table
        v-loading="loading"
        :data="treeRows"
        row-key="treeKey"
        default-expand-all
        stripe
        show-overflow-tooltip
        :tree-props="{ children: 'children' }"
      >
        <el-table-column prop="name" label="名称" min-width="180">
          <template #default="{ row }">
            <span :class="{ 'project-row-name': row.nodeType === 'project' }">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" min-width="90">
          <template #default="{ row }">
            <el-tag v-if="row.nodeType === 'program'" type="primary">项目集</el-tag>
            <el-tag v-else type="success">项目</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="负责人" min-width="120">
          <template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template>
        </el-table-column>
        <el-table-column prop="department" label="部门" min-width="110" />
        <el-table-column prop="status" label="状态" min-width="90" />
        <el-table-column label="操作" min-width="200">
          <template #default="{ row }">
            <template v-if="row.nodeType === 'program'">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="success" @click="openCreate(row.id)">新增项目集</el-button>
              <el-popconfirm title="确认删除该项目集？" @confirm="removeProgram(row.id)">
                <template #reference><el-button link type="danger">删除</el-button></template>
              </el-popconfirm>
            </template>
            <template v-else>
              <span class="muted-action">在项目页维护</span>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px">
      <el-form label-position="top">
        <el-form-item label="项目集名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人">
            <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门"><el-input v-model="form.department" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="启用" value="active" />
            <el-option label="关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitProgram">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createProgram, deleteProgram, fetchProgramTree, updateProgram } from '../api/programs'
import { fetchUsers } from '../api/users'
import { userLabel } from '../utils/referenceLabels'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const programTree = ref([])
const users = ref([])
const form = reactive({ parent_id: null, name: '', owner_id: null, department: '', status: 'active', description: '' })

const dialogTitle = computed(() => {
  if (editingId.value) return '编辑项目集'
  return '新增项目集'
})

const treeRows = computed(() => programTree.value.map(toTreeRow))

function toTreeRow(node) {
  return {
    ...node,
    treeKey: `program-${node.id}`,
    nodeType: 'program',
    children: [
      ...(node.children || []).map(toTreeRow),
      ...(node.projects || []).map((project) => ({
        ...project,
        treeKey: `project-${project.id}`,
        nodeType: 'project',
        program_id: node.id,
        children: []
      }))
    ]
  }
}

function resetForm(parentId = null) {
  Object.assign(form, { parent_id: parentId, name: '', owner_id: null, department: '', status: 'active', description: '' })
}

function openCreate(parentId = null) {
  editingId.value = null
  resetForm(parentId)
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    parent_id: row.parent_id,
    name: row.name,
    owner_id: row.owner_id,
    department: row.department || '',
    status: row.status,
    description: row.description || ''
  })
  dialogVisible.value = true
}

async function loadData() {
  loading.value = true
  try {
    const [treeRes, userRes] = await Promise.all([fetchProgramTree(), fetchUsers()])
    programTree.value = treeRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('项目集树加载失败')
  } finally {
    loading.value = false
  }
}

async function submitProgram() {
  if (!form.name.trim()) return ElMessage.warning('请填写项目集名称')
  saving.value = true
  try {
    const payload = { ...form, parent_id: form.parent_id || null, owner_id: form.owner_id || null }
    if (editingId.value) await updateProgram(editingId.value, payload)
    else await createProgram(payload)
    dialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function removeProgram(id) {
  await deleteProgram(id)
  await loadData()
}

onMounted(loadData)
</script>
