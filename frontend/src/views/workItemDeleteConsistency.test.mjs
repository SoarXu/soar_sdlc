import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const taskDetail = readFileSync(new URL('./TaskDetailView.vue', import.meta.url), 'utf8')
const taskList = readFileSync(new URL('./TasksView.vue', import.meta.url), 'utf8')
const projectDetail = readFileSync(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')
const requirements = readFileSync(new URL('./RequirementsView.vue', import.meta.url), 'utf8')

assert.match(taskList, /function canDeleteTaskRow\(row\)[\s\S]*?canDeleteWorkItem/, '全局任务列表应使用统一的工作项删除权限判断')
assert.match(projectDetail, /<el-popconfirm v-if="canDeleteCurrentWorkItem && !projectClosed" title="确认删除该任务？"/, '项目任务列表不得因任务已完成隐藏删除入口')
assert.match(taskDetail, /canDeleteWorkItem/, '任务详情应使用统一的工作项删除权限判断')

assert.match(taskDetail, /deleteTask/, '任务详情应调用任务删除接口')
assert.match(taskDetail, /确认删除该任务？/, '任务详情应通过确认交互删除任务')
assert.match(taskDetail, /showActionError\(error, '任务删除失败'\)/, '任务详情删除失败应展示后端错误')
assert.match(requirements, /showActionError\(error, '需求删除失败'\)/, '需求删除冲突应展示后端说明')

assert.doesNotMatch(
  taskDetail,
  /<el-popconfirm[^>]*v-if="!editing && canDeleteTask"[\s\S]*?<template v-else>/,
  '删除入口不得截断编辑态的 v-else 分支'
)

console.log('work item delete consistency tests passed')
