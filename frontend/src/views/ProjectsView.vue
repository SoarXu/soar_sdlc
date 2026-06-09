<template>
  <section>
    <div class="page-head">
      <div>
        <h1>项目管理</h1>
        <p>设置项目负责人后，可按工作流同步需求和任务负责人。</p>
      </div>
      <el-button type="primary" @click="dialogVisible = true">新增项目</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="projects" stripe>
        <el-table-column prop="code" label="编号" width="140" />
        <el-table-column prop="name" label="项目名称" />
        <el-table-column prop="owner" label="负责人" width="160" />
        <el-table-column prop="status" label="状态" width="120" />
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="新增项目" width="460px">
      <el-form label-position="top">
        <el-form-item label="项目编号">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="form.owner" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProject">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createProject, fetchProjects } from '../api/projects'

const loading = ref(false)
const dialogVisible = ref(false)
const projects = ref([])
const form = reactive({
  code: '',
  name: '',
  owner: ''
})

async function loadProjects() {
  loading.value = true
  try {
    const { data } = await fetchProjects()
    projects.value = data
  } catch (error) {
    ElMessage.error('项目列表加载失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}

async function submitProject() {
  await createProject({ ...form })
  dialogVisible.value = false
  form.code = ''
  form.name = ''
  form.owner = ''
  await loadProjects()
}

onMounted(loadProjects)
</script>
