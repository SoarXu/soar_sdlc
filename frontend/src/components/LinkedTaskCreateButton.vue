<template>
  <el-button type="primary" :icon="Plus" @click="openDialog">创建关联任务</el-button>

  <el-dialog v-model="visible" title="创建关联任务" width="620px">
    <el-form label-position="top">
      <el-form-item label="任务标题" required>
        <el-input v-model="form.title" />
      </el-form-item>
      <div class="form-grid">
        <el-form-item label="优先级">
          <el-select v-model="form.priority">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="指定处理人">
          <el-select v-model="form.owner_id" clearable filterable>
            <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
          </el-select>
        </el-form-item>
      </div>
      <el-form-item v-if="form.owner_id" label="覆盖原因" required>
        <el-input v-model="form.override_reason" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="任务描述">
        <el-input v-model="form.description" type="textarea" :rows="4" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { createLinkedTask } from '../api/tasks'
import { showActionError } from '../utils/actionFeedback'

const props = defineProps({
  sourceType: { type: String, required: true },
  sourceId: { type: Number, required: true },
  sourceTitle: { type: String, default: '' },
  users: { type: Array, default: () => [] }
})
const emit = defineEmits(['created'])
const visible = ref(false)
const saving = ref(false)
const form = reactive({ title: '', priority: 'medium', owner_id: null, override_reason: '', description: '' })

function openDialog() {
  Object.assign(form, {
    title: props.sourceTitle ? `${props.sourceTitle} - 执行任务` : '',
    priority: 'medium',
    owner_id: null,
    override_reason: '',
    description: ''
  })
  visible.value = true
}

async function submit() {
  if (!form.title.trim()) return ElMessage.warning('请填写任务标题')
  if (form.owner_id && !form.override_reason.trim()) return ElMessage.warning('请填写处理人覆盖原因')
  saving.value = true
  try {
    const { data } = await createLinkedTask({
      source_type: props.sourceType,
      source_id: props.sourceId,
      title: form.title.trim(),
      priority: form.priority,
      owner_id: form.owner_id || null,
      override_reason: form.override_reason.trim() || null,
      description: form.description || null
    })
    visible.value = false
    ElMessage.success('关联任务已创建')
    emit('created', data)
  } catch (error) {
    showActionError(error, '关联任务创建失败')
  } finally {
    saving.value = false
  }
}
</script>
