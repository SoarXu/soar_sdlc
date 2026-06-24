<template>
  <section class="project-detail-page">
    <div class="project-detail-head">
      <div>
        <el-button link type="primary" @click="$router.push('/projects')">返回项目列表</el-button>
        <h1>{{ project.name || '项目详情' }}</h1>
        <p>
          {{ labelById(programs, project.program_id) }} · {{ userLabel(users, project.owner_id) }} ·
          计划 {{ project.start_date || '未设置开始' }} 至 {{ projectEndDateLabel }}
        </p>
      </div>
      <el-tag size="large">{{ projectStatusLabel(project.status) }}</el-tag>
    </div>

    <div class="project-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="project-tab-button"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="setActiveTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>
    <el-card v-loading="loading" shadow="never" class="project-detail-card">
      <template v-if="activeTab === 'overview'">
        <div class="project-overview">
        <div class="metrics project-detail-metrics">
          <el-card v-for="item in metrics" :key="item.key" shadow="never">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </el-card>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="项目名称">{{ project.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属项目集">{{ labelById(programs, project.program_id) }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ userLabel(users, project.owner_id) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ projectStatusLabel(project.status) }}</el-descriptions-item>
          <el-descriptions-item label="计划开始">{{ project.start_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="计划结束">{{ projectEndDateLabel }}</el-descriptions-item>
          <el-descriptions-item label="实际开始">{{ project.actual_start_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际结束">{{ project.actual_end_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ project.description || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div class="project-history">
          <h2>历史记录</h2>
          <el-empty v-if="!projectHistory.length" description="暂无历史记录" />
          <div v-else class="project-history-list">
            <div v-for="(item, index) in projectHistory" :key="item.key" class="project-history-entry">
              <div
                class="project-history-line"
                :class="{ expandable: item.type === 'audit' }"
                @click="item.type === 'audit' && toggleHistory(item.key)"
              >
                <span class="project-history-index">{{ index + 1 }}</span>
                <span>{{ formatDateTime(item.time) }}，由 {{ item.actor }} {{ item.actionLabel }}。</span>
                <button
                  v-if="item.type === 'audit'"
                  class="project-history-toggle"
                  type="button"
                  @click.stop="toggleHistory(item.key)"
                >
                  {{ isHistoryExpanded(item.key) ? '-' : '+' }}
                </button>
              </div>
              <div v-if="item.type === 'audit' && isHistoryExpanded(item.key)" class="project-history-detail">
                <p v-for="change in item.changes" :key="change.field">
                  修改了 <strong>{{ projectFieldLabel(change.field) }}</strong>，旧值为 "{{ displayHistoryValue(change.field, change.oldValue) }}"，新值为 "{{ displayHistoryValue(change.field, change.newValue) }}"。
                </p>
              </div>
            </div>
          </div>
        </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'iterations'">
        <div class="project-tab-toolbar">
          <el-input v-model="projectListFilters.iterations.keyword" clearable placeholder="搜索迭代名称" class="project-tab-search" @keyup.enter="resetProjectListSearch('iterations')" @clear="resetProjectListSearch('iterations')" />
          <el-button type="primary" @click="openIterationCreate">新增迭代</el-button>
        </div>
        <el-table :data="pagedProjectIterations" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="name" label="迭代名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column prop="start_date" label="开始日期" width="130" />
          <el-table-column prop="end_date" label="结束日期" width="130" />
          <el-table-column prop="actual_start_date" label="实际开始" width="130" />
          <el-table-column prop="actual_end_date" label="实际结束" width="130" />
          <el-table-column label="状态" width="120"><template #default="{ row }">{{ iterationStatusLabel(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="250" fixed="right">
            <template #default="{ row }"><el-button v-if="row.status === 'planning'" link type="success" @click="openIterationStart(row)">开始</el-button><el-button v-if="row.status === 'active'" link type="warning" @click="openIterationFinish(row)">结束</el-button><el-button link type="primary" @click="openIterationEdit(row)">编辑</el-button><el-popconfirm title="确认删除该迭代？" @confirm="removeIteration(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
          </el-table-column>
        </el-table>
        <div class="table-pagination">
          <el-pagination
            v-model:current-page="projectListPagination.iterations.currentPage"
            v-model:page-size="projectListPagination.iterations.pageSize"
            :page-sizes="projectPageSizes"
            :total="projectListTotals.iterations"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="loadProjectIterationsPage"
            @size-change="resetProjectListSearch('iterations')"
          />
        </div>
      </template>

      <template v-else-if="activeTab === 'requirements'">
        <div class="project-tab-toolbar">
          <el-input v-model="projectListFilters.requirements.keyword" clearable placeholder="搜索需求标题" class="project-tab-search" @keyup.enter="resetProjectListSearch('requirements')" @clear="resetProjectListSearch('requirements')" />
          <el-button type="primary" :disabled="projectClosed" @click="openRequirementCreate">新增需求</el-button>
        </div>
        <el-table :data="pagedProjectRequirements" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="需求标题" min-width="180" show-overflow-tooltip>
            <template #default="{ row }"><router-link class="table-link" :to="`/requirements/${row.id}`">{{ row.title }}</router-link></template>
          </el-table-column>
          <el-table-column label="迭代" width="140"><template #default="{ row }">{{ labelById(projectIterationOptions, row.iteration_id) }}</template></el-table-column>
          <el-table-column label="负责人" width="130"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column label="优先级" width="100"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
          <el-table-column label="评审状态" width="110"><template #default="{ row }">{{ reviewStatusLabel(row.review_status) }}</template></el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tooltip v-if="closeReasonByRequirement[row.id]" :content="closeReasonByRequirement[row.id]" placement="top" raw-content>
                <span class="status-with-reason">{{ requirementStatusLabel(row.status) }}</span>
              </el-tooltip>
              <span v-else>{{ requirementStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="360" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
              <el-button link type="primary" :disabled="projectClosed" @click="openRequirementEdit(row)">编辑</el-button>
              <el-button v-if="canActivateRequirement(row)" link type="warning" @click="activateRequirementRow(row.id)">激活</el-button>
              <el-button v-if="row.status === 'active'" link type="danger" @click="openRequirementClose(row)">关闭</el-button>
              <el-button link type="success" :disabled="projectClosed" @click="openGenerate(row)">生成任务</el-button>
              <el-button link type="success" :disabled="projectClosed" @click="openCaseCreateForRequirement(row)">建用例</el-button>
              <el-popconfirm title="确认删除该需求？" :disabled="projectClosed" @confirm="removeRequirement(row.id)"><template #reference><el-button link type="danger" :disabled="projectClosed">删除</el-button></template></el-popconfirm>
              </div>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-pagination">
          <el-pagination
            v-model:current-page="projectListPagination.requirements.currentPage"
            v-model:page-size="projectListPagination.requirements.pageSize"
            :page-sizes="projectPageSizes"
            :total="projectListTotals.requirements"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="loadProjectRequirementsPage"
            @size-change="resetProjectListSearch('requirements')"
          />
        </div>
      </template>

      <template v-else-if="activeTab === 'tasks'">
        <div class="project-tab-toolbar">
          <el-input v-model="projectListFilters.tasks.keyword" clearable placeholder="搜索任务标题" class="project-tab-search" @keyup.enter="resetProjectListSearch('tasks')" @clear="resetProjectListSearch('tasks')" />
          <el-button type="primary" :disabled="projectClosed" @click="openTaskCreate">新增任务</el-button>
        </div>
        <el-table :data="pagedProjectTasks" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="任务标题" min-width="180" show-overflow-tooltip>
            <template #default="{ row }"><router-link class="table-link" :to="`/tasks/${row.id}`">{{ row.title }}</router-link></template>
          </el-table-column>
          <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(projectRequirementOptions, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column prop="actual_hours" label="实际工时" width="110" />
          <el-table-column prop="due_date" label="截止日期" width="130" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tooltip v-if="closeReasonByTask[row.id]" :content="closeReasonByTask[row.id]" placement="top" raw-content>
                <span class="status-with-reason">{{ taskStatusLabel(row.status) }}</span>
              </el-tooltip>
              <span v-else>{{ taskStatusLabel(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }"><el-button link type="primary" :disabled="projectClosed" @click="openTaskEdit(row)">编辑</el-button><el-button v-if="canActivateTask(row)" link type="warning" @click="activateTaskRow(row.id)">激活</el-button><el-button v-if="row.status !== 'closed'" link type="danger" @click="openTaskClose(row)">关闭</el-button><el-popconfirm title="确认删除该任务？" :disabled="projectClosed" @confirm="removeTask(row.id)"><template #reference><el-button link type="danger" :disabled="projectClosed">删除</el-button></template></el-popconfirm></template>
          </el-table-column>
        </el-table>
        <div class="table-pagination">
          <el-pagination
            v-model:current-page="projectListPagination.tasks.currentPage"
            v-model:page-size="projectListPagination.tasks.pageSize"
            :page-sizes="projectPageSizes"
            :total="projectListTotals.tasks"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="loadProjectTasksPage"
            @size-change="resetProjectListSearch('tasks')"
          />
        </div>
      </template>

      <template v-else-if="activeTab === 'tests'">
        <el-tabs v-model="testTab">
          <el-tab-pane label="测试用例" name="cases">
            <div class="project-tab-toolbar">
              <el-input v-model="projectListFilters.testCases.keyword" clearable placeholder="搜索用例标题" class="project-tab-search" @keyup.enter="resetProjectListSearch('testCases')" @clear="resetProjectListSearch('testCases')" />
              <el-button type="primary" @click="openCaseCreate">新增用例</el-button>
            </div>
            <el-table :data="pagedProjectTestCases" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column label="用例标题" min-width="180" show-overflow-tooltip><template #default="{ row }"><router-link class="table-link" :to="{ name: 'test-case-detail', params: { id: row.id }, query: { from: 'project' } }">{{ row.title }}</router-link></template></el-table-column>
              <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(projectRequirementOptions, row.requirement_id, 'title') }}</template></el-table-column>
              <el-table-column label="最近执行时间" width="170"><template #default="{ row }">{{ formatDateTime(row.last_execute_time) }}</template></el-table-column>
              <el-table-column label="最近结果" width="110"><template #default="{ row }">{{ executionResultLabel(row.last_execute_result) }}</template></el-table-column>
              <el-table-column label="操作" width="280" fixed="right"><template #default="{ row }"><el-button link type="success" @click="openCaseExecution(row)">执行</el-button><el-button link type="warning" :disabled="!canCreateBugFromCase(row)" @click="openCaseBug(row)">提 Bug</el-button><el-button link type="primary" @click="openCaseEdit(row)">编辑</el-button><el-popconfirm title="确认删除该用例？" @confirm="removeCase(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template></el-table-column>
            </el-table>
            <div class="table-pagination">
              <el-pagination
                v-model:current-page="projectListPagination.testCases.currentPage"
                v-model:page-size="projectListPagination.testCases.pageSize"
                :page-sizes="projectPageSizes"
                :total="projectListTotals.testCases"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="loadProjectTestCasesPage"
                @size-change="resetProjectListSearch('testCases')"
              />
            </div>
          </el-tab-pane>
          <el-tab-pane label="测试单" name="runs">
            <div class="project-tab-toolbar">
              <el-input v-model="projectListFilters.testRuns.keyword" clearable placeholder="搜索测试单名称" class="project-tab-search" @keyup.enter="resetProjectListSearch('testRuns')" @clear="resetProjectListSearch('testRuns')" />
              <el-button type="primary" @click="openRunCreate">新增测试单</el-button>
            </div>
            <el-table :data="pagedProjectTestRuns" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="测试单名称" min-width="180" show-overflow-tooltip />
              <el-table-column label="迭代" width="160"><template #default="{ row }">{{ labelById(projectIterationOptions, row.iteration_id) }}</template></el-table-column>
              <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.test_owner_id) }}</template></el-table-column>
              <el-table-column label="状态" width="110"><template #default="{ row }">{{ testRunStatusLabel(row.status) }}</template></el-table-column>
              <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openRunEdit(row)">编辑</el-button><el-popconfirm title="确认删除该测试单？" @confirm="removeRun(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template></el-table-column>
            </el-table>
            <div class="table-pagination">
              <el-pagination
                v-model:current-page="projectListPagination.testRuns.currentPage"
                v-model:page-size="projectListPagination.testRuns.pageSize"
                :page-sizes="projectPageSizes"
                :total="projectListTotals.testRuns"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="loadProjectTestRunsPage"
                @size-change="resetProjectListSearch('testRuns')"
              />
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>

      <template v-else-if="activeTab === 'bugs'">
        <div class="project-tab-toolbar">
          <el-input v-model="projectListFilters.bugs.keyword" clearable placeholder="搜索 Bug 标题/类型" class="project-tab-search" @keyup.enter="resetProjectListSearch('bugs')" @clear="resetProjectListSearch('bugs')" />
          <el-button type="primary" @click="openBugCreate">新增 Bug</el-button>
        </div>
        <el-table :data="pagedProjectBugs" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="Bug 标题" min-width="180" show-overflow-tooltip><template #default="{ row }"><router-link class="table-link" :to="{ name: 'bug-detail', params: { id: row.id }, query: { from: 'project' } }">{{ row.title }}</router-link></template></el-table-column>
          <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(projectRequirementOptions, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column label="任务" width="180"><template #default="{ row }">{{ labelById(projectTaskOptions, row.task_id, 'title') }}</template></el-table-column>
          <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column label="Bug 类型" width="120"><template #default="{ row }">{{ row.bug_type || '-' }}</template></el-table-column>
          <el-table-column label="严重程度" width="110"><template #default="{ row }"><RequirementPriorityBadge :value="row.severity" /></template></el-table-column>
          <el-table-column label="优先级" width="110"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
          <el-table-column label="状态" width="120"><template #default="{ row }">{{ bugStatusLabel(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="380" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <el-button link type="primary" @click="openBugEdit(row)">编辑</el-button>
                <el-button v-if="['open', 'reopened', 'suspended'].includes(row.status)" link type="success" @click="openBugAction(row, 'start_fixing')">确认</el-button>
                <el-button v-if="row.status === 'fixing'" link type="success" @click="openBugAction(row, 'resolve')">解决</el-button>
                <el-button v-if="['verifying', 'closed'].includes(row.status)" link type="warning" @click="openBugAction(row, 'activate')">激活</el-button>
                <el-button v-if="['open', 'fixing', 'reopened'].includes(row.status)" link type="warning" @click="openBugAction(row, 'suspend')">挂起</el-button>
                <el-button v-if="['open', 'suspended', 'verifying'].includes(row.status)" link type="danger" @click="openBugAction(row, 'close')">关闭</el-button>
                <el-popconfirm title="确认删除该 Bug？" @confirm="removeBug(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
              </div>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-pagination">
          <el-pagination
            v-model:current-page="projectListPagination.bugs.currentPage"
            v-model:page-size="projectListPagination.bugs.pageSize"
            :page-sizes="projectPageSizes"
            :total="projectListTotals.bugs"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="loadProjectBugsPage"
            @size-change="resetProjectListSearch('bugs')"
          />
        </div>
      </template>

      <template v-else-if="activeTab === 'members'">
        <div class="project-tab-toolbar">
          <el-button type="primary" @click="addProjectMember">添加成员</el-button>
          <el-button type="success" :loading="saving" @click="submitProjectMembers">保存成员</el-button>
        </div>
        <el-table :data="projectMembers" stripe width="100%">
          <el-table-column label="成员" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.user_id" clearable filterable>
                <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="项目角色" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.project_role">
                <el-option v-for="option in projectMemberRoleOptions" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="默认分配" width="120" align="center">
            <template #default="{ row }"><el-checkbox v-model="row.is_default_assignee" /></template>
          </el-table-column>
          <el-table-column label="工作台" width="120" align="center">
            <template #default="{ row }"><el-checkbox v-model="row.is_workbench_participant" /></template>
          </el-table-column>
          <el-table-column label="排序" width="120">
            <template #default="{ row }"><el-input-number v-model="row.sort_order" :min="0" controls-position="right" /></template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ $index }"><el-button link type="danger" @click="removeProjectMember($index)">删除</el-button></template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else>
        <div class="project-tab-placeholder">
          <h2>{{ activeTabLabel }}</h2>
          <p>该分类将在后续版本承载当前项目下的{{ activeTabLabel }}数据。</p>
        </div>
      </template>
    </el-card>

    <el-dialog v-model="iterationDialogVisible" :title="editingIterationId ? '编辑迭代' : '新增迭代'" width="560px">
      <el-form label-position="top">
        <el-form-item label="迭代名称" required><el-input v-model="iterationForm.name" /></el-form-item>
        <div class="form-grid"><el-form-item label="负责人"><el-select v-model="iterationForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="状态"><el-select v-model="iterationForm.status"><el-option label="规划中" value="planning" /><el-option label="进行中" value="active" /><el-option label="已完成" value="finished" /><el-option label="已关闭" value="closed" /></el-select></el-form-item><el-form-item label="开始日期"><el-date-picker v-model="iterationForm.start_date" value-format="YYYY-MM-DD" type="date" /></el-form-item><el-form-item label="结束日期"><el-date-picker v-model="iterationForm.end_date" value-format="YYYY-MM-DD" type="date" /></el-form-item></div>
        <el-form-item label="目标"><el-input v-model="iterationForm.goal" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="iterationDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitIteration">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="iterationStartVisible" title="开始迭代" width="480px">
      <el-form label-position="top">
        <el-form-item label="实际开始日期" required><el-date-picker v-model="iterationStartForm.effective_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="iterationStartForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="iterationStartVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitIterationStart">确认开始</el-button></template>
    </el-dialog>
    <el-dialog v-model="iterationFinishVisible" title="结束迭代" width="480px">
      <el-form label-position="top">
        <el-form-item label="实际结束日期" required><el-date-picker v-model="iterationFinishForm.effective_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="iterationFinishForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="iterationFinishVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitIterationFinish">确认结束</el-button></template>
    </el-dialog>

    <el-dialog v-model="requirementDialogVisible" :title="editingRequirementId ? '编辑需求' : '新增需求'" width="640px">
      <el-form label-position="top">
        <el-form-item label="需求标题" required><el-input v-model="requirementForm.title" /></el-form-item>
        <div class="form-grid"><el-form-item label="迭代"><el-select v-model="requirementForm.iteration_id" clearable filterable><el-option v-for="iteration in projectIterationOptions" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item><el-form-item label="负责人"><el-select v-model="requirementForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="提出人"><el-select v-model="requirementForm.proposer_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="类型"><el-select v-model="requirementForm.requirement_type"><el-option v-for="option in requirementTypeOptions" :key="option" :label="option" :value="option" /></el-select></el-form-item><el-form-item label="优先级"><el-select v-model="requirementForm.priority" class="priority-select"><template #prefix><RequirementPriorityBadge :value="requirementForm.priority" /></template><el-option v-for="option in requirementPriorityOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item><el-form-item label="评审状态"><el-select v-model="requirementForm.review_status"><el-option label="无需评审" value="not_required" /><el-option label="待评审" value="pending" /><el-option label="已通过" value="approved" /></el-select></el-form-item></div>
        <el-form-item label="需求描述"><el-input v-model="requirementForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="requirementForm.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="requirementDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirement">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="closeRequirementVisible" title="关闭需求" width="480px">
      <el-form label-position="top">
        <el-form-item label="关闭原因" required>
          <el-select v-model="closeRequirementForm.reason" placeholder="请选择关闭原因">
            <el-option v-for="option in requirementCloseReasons" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="closeRequirementForm.remark" type="textarea" :rows="3" placeholder="补充说明本次关闭原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeRequirementVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitRequirementClose">确认关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="taskDialogVisible" :title="editingTaskId ? '编辑任务' : '新增任务'" width="620px">
      <el-form label-position="top">
        <el-form-item label="任务标题" required><el-input v-model="taskForm.title" /></el-form-item>
        <div class="form-grid"><el-form-item label="需求"><el-select v-model="taskForm.requirement_id" clearable filterable @change="onTaskRequirementChange"><el-option v-for="requirement in projectRequirementOptions" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item><el-form-item label="负责人"><el-select v-model="taskForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="类型"><el-input v-model="taskForm.task_type" /></el-form-item><el-form-item label="优先级"><el-select v-model="taskForm.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item><el-form-item label="预计工时"><el-input-number v-model="taskForm.estimated_hours" :min="0" /></el-form-item><el-form-item label="实际工时"><el-input-number v-model="taskForm.actual_hours" :min="0" /></el-form-item><el-form-item label="截止日期"><el-date-picker v-model="taskForm.due_date" value-format="YYYY-MM-DD" type="date" /></el-form-item><el-form-item label="状态"><el-select v-model="taskForm.status"><el-option label="待办" value="todo" /><el-option label="进行中" value="doing" /><el-option label="完成" value="done" /><el-option label="关闭" value="closed" /></el-select></el-form-item></div>
        <el-form-item label="描述"><el-input v-model="taskForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="taskDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTask">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="closeTaskVisible" title="关闭任务" width="480px">
      <el-form label-position="top">
        <el-form-item label="关闭原因" required>
          <el-select v-model="closeTaskForm.reason" placeholder="请选择关闭原因">
            <el-option v-for="option in closeReasons" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="closeTaskForm.remark" type="textarea" :rows="3" placeholder="补充说明本次关闭原因" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="closeTaskVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTaskClose">确认关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="caseDialogVisible" :title="editingCaseId ? '编辑用例' : '新增用例'" width="760px">
      <el-form label-position="top">
        <el-form-item label="用例标题" required><el-input v-model="caseForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="需求"><el-select v-model="caseForm.requirement_id" clearable filterable><el-option v-for="requirement in projectRequirementOptions" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
          <el-form-item label="测试人"><el-select v-model="caseForm.default_tester_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="用例类型"><el-select v-model="caseForm.case_type"><el-option v-for="option in caseTypeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
          <el-form-item label="适用范围"><el-select v-model="caseForm.test_scope"><el-option v-for="option in testScopeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        </div>
        <el-form-item label="前置条件"><el-input v-model="caseForm.precondition" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="用例步骤">
          <div class="case-steps-editor">
            <el-table :data="caseForm.steps_json" border>
              <el-table-column label="步骤" min-width="260"><template #default="{ row, $index }"><el-input v-model="row.step" :placeholder="`步骤 ${$index + 1}`" /></template></el-table-column>
              <el-table-column label="预期" min-width="260"><template #default="{ row }"><el-input v-model="row.expected" placeholder="预期结果" /></template></el-table-column>
              <el-table-column label="操作" width="90"><template #default="{ $index }"><el-button link type="danger" :disabled="caseForm.steps_json.length === 1" @click="removeCaseStep($index)">删除</el-button></template></el-table-column>
            </el-table>
            <el-button class="case-step-add" @click="addCaseStep">增加步骤</el-button>
          </div>
        </el-form-item>
        <el-form-item label="预期结果"><el-input v-model="caseForm.expected_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="caseDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCase">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="caseExecutionVisible" :title="`执行用例 ${selectedCase?.title || ''}`" width="980px">
      <el-form label-position="top">
        <el-form-item label="执行时间"><el-date-picker v-model="caseExecutionForm.execute_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" /></el-form-item>
        <el-table :data="caseExecutionForm.steps_result_json" border>
          <el-table-column prop="step" label="步骤" min-width="220" />
          <el-table-column prop="expected" label="预期" min-width="220" />
          <el-table-column label="测试结果" width="140"><template #default="{ row }"><el-select v-model="row.result"><el-option v-for="option in executionResultOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></template></el-table-column>
          <el-table-column label="实际情况" min-width="220"><template #default="{ row }"><el-input v-model="row.actual" type="textarea" :rows="1" /></template></el-table-column>
        </el-table>
      </el-form>
      <div class="execution-history">
        <h3>测试结果</h3>
        <p>共执行 {{ caseExecutionHistory.length }} 次，失败 {{ failedExecutionCount }} 次</p>
        <el-collapse>
          <el-collapse-item v-for="item in caseExecutionHistory" :key="item.id" :title="executionHistoryTitle(item)" :name="item.id">
            <el-table :data="item.steps_result_json || []" border>
              <el-table-column prop="step" label="步骤" min-width="220" />
              <el-table-column prop="expected" label="预期" min-width="220" />
              <el-table-column label="测试结果" width="120"><template #default="{ row }">{{ executionResultLabel(row.result) }}</template></el-table-column>
              <el-table-column prop="actual" label="实际情况" min-width="220" />
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>
      <template #footer><el-button @click="caseExecutionVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseExecution">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="caseBugVisible" title="提交 Bug" width="820px">
      <el-form label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="caseBugForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="Bug 类型"><el-select v-model="caseBugForm.bug_type"><el-option v-for="option in bugTypeOptions" :key="option" :label="option" :value="option" /></el-select></el-form-item>
          <el-form-item label="严重程度"><el-select v-model="caseBugForm.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="caseBugForm.priority"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
        </div>
        <el-form-item label="重现步骤"><RichTextPasteEditor v-model="caseBugForm.reproduce_steps" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="caseBugForm.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="caseBugVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseBug">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="runDialogVisible" :title="editingRunId ? '编辑测试单' : '新增测试单'" width="560px">
      <el-form label-position="top"><el-form-item label="测试单名称" required><el-input v-model="runForm.name" /></el-form-item><div class="form-grid"><el-form-item label="迭代"><el-select v-model="runForm.iteration_id" clearable filterable><el-option v-for="iteration in projectIterationOptions" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item><el-form-item label="测试负责人"><el-select v-model="runForm.test_owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="状态"><el-select v-model="runForm.status"><el-option label="规划中" value="planning" /><el-option label="执行中" value="running" /><el-option label="完成" value="finished" /></el-select></el-form-item></div><el-form-item label="备注"><el-input v-model="runForm.remark" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="runDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRun">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="bugDialogVisible" :title="editingBugId ? '编辑 Bug' : '新增 Bug'" width="700px">
      <el-form label-position="top"><el-form-item label="Bug 标题" required><el-input v-model="bugForm.title" /></el-form-item><div class="form-grid"><el-form-item label="需求"><el-select v-model="bugForm.requirement_id" clearable filterable><el-option v-for="requirement in projectRequirementOptions" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item><el-form-item label="任务"><el-select v-model="bugForm.task_id" clearable filterable><el-option v-for="task in projectTaskOptions" :key="task.id" :label="task.title" :value="task.id" /></el-select></el-form-item><el-form-item label="来源用例"><el-select v-model="bugForm.test_case_id" clearable filterable><el-option v-for="item in projectTestCaseOptions" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item><el-form-item label="来源测试单"><el-select v-model="bugForm.test_run_id" clearable filterable><el-option v-for="run in projectTestRunOptions" :key="run.id" :label="run.name" :value="run.id" /></el-select></el-form-item><el-form-item label="所属迭代"><el-select v-model="bugForm.iteration_id" clearable filterable><el-option v-for="iteration in projectIterationOptions" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item><el-form-item label="Bug 类型"><el-select v-model="bugForm.bug_type"><el-option v-for="option in bugTypeOptions" :key="option" :label="option" :value="option" /></el-select></el-form-item><el-form-item label="负责人"><el-select v-model="bugForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="提出人"><el-select v-model="bugForm.reporter_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="严重程度"><el-select v-model="bugForm.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item><el-form-item label="优先级"><el-select v-model="bugForm.priority"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item></div><el-form-item label="复现步骤"><RichTextPasteEditor v-model="bugForm.reproduce_steps" /></el-form-item><el-form-item label="期望结果"><el-input v-model="bugForm.expected_result" type="textarea" :rows="2" /></el-form-item><el-form-item label="实际结果"><el-input v-model="bugForm.actual_result" type="textarea" :rows="2" /></el-form-item></el-form>
      <template #footer><el-button @click="bugDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitBug">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="bugActionVisible" :title="bugActionTitle" width="480px">
      <el-form label-position="top">
        <el-form-item v-if="bugActionType === 'resolve'" label="解决结果" required>
          <el-select v-model="bugActionForm.resolution">
            <el-option v-for="option in bugResolutionOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="bugActionType === 'start_fixing'" label="解决迭代">
          <el-select v-model="bugActionForm.iteration_id" clearable filterable placeholder="请选择解决迭代">
            <el-option v-for="iteration in projectIterationOptions" :key="iteration.id" :label="iteration.name" :value="iteration.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="bugActionType === 'suspend'" label="原因">
          <el-input v-model="bugActionForm.reason" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="bugActionForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="bugActionVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitBugAction">确认</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { activateBug, closeBug, createBug, deleteBug, resolveBug, startFixingBug, suspendBug, updateBug } from '../api/bugs'
import { createIteration, deleteIteration, fetchIterations, finishIteration, startIteration, updateIteration } from '../api/iterations'
import { fetchPrograms } from '../api/programs'
import {
  fetchProject,
  fetchProjectAuditLogs,
  fetchProjectBugs,
  fetchProjectIterations,
  fetchProjectMembers,
  fetchProjectRequirements,
  fetchProjectStatusOperations,
  fetchProjectTasks,
  fetchProjectTestCases,
  fetchProjectTestRuns,
  fetchProjects,
  saveProjectMembers
} from '../api/projects'
import { activateRequirement, closeRequirement, createRequirement, deleteRequirement, fetchRequirementStatusOperations, fetchRequirements, updateRequirement } from '../api/requirements'
import { activateTask, closeTask, createTask, deleteTask, fetchTaskStatusOperations, fetchTasks, updateTask } from '../api/tasks'
import { createBugFromTestCase, createTestCase, deleteTestCase, executeTestCase, fetchTestCaseExecutions, updateTestCase } from '../api/testCases'
import { createTestRun, deleteTestRun, updateTestRun } from '../api/testRuns'
import { fetchUsers } from '../api/users'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import { currentUserId } from '../utils/currentUser'
import { loadCloseReasonMap } from '../utils/closeReasonTooltip'
import { labelById, userLabel } from '../utils/referenceLabels'
import { formatAuditValue } from '../utils/auditHistoryLabels'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const activeTab = ref(normalizeProjectTab(route.query.tab))
const testTab = ref('cases')
const project = ref({})
const projects = ref([])
const programs = ref([])
const users = ref([])
const iterations = ref([])
const requirements = ref([])
const tasks = ref([])
const testCases = ref([])
const testRuns = ref([])
const bugs = ref([])
const projectIterationRows = ref([])
const projectRequirementRows = ref([])
const projectTaskRows = ref([])
const projectTestCaseRows = ref([])
const projectTestRunRows = ref([])
const projectBugRows = ref([])
const projectMembers = ref([])
const projectAuditLogs = ref([])
const projectStatusOperations = ref([])
const closeReasonByRequirement = ref({})
const closeReasonByTask = ref({})
const expandedHistoryKeys = ref(new Set())
const projectPageSizes = [10, 20, 50, 100]
const projectListTotals = reactive({
  iterations: 0,
  requirements: 0,
  tasks: 0,
  testCases: 0,
  testRuns: 0,
  bugs: 0
})
const projectListFilters = reactive({
  iterations: { keyword: '' },
  requirements: { keyword: '' },
  tasks: { keyword: '' },
  testCases: { keyword: '' },
  testRuns: { keyword: '' },
  bugs: { keyword: '' }
})
const projectListPagination = reactive({
  iterations: { currentPage: 1, pageSize: 10 },
  requirements: { currentPage: 1, pageSize: 10 },
  tasks: { currentPage: 1, pageSize: 10 },
  testCases: { currentPage: 1, pageSize: 10 },
  testRuns: { currentPage: 1, pageSize: 10 },
  bugs: { currentPage: 1, pageSize: 10 }
})

const iterationDialogVisible = ref(false), iterationStartVisible = ref(false), iterationFinishVisible = ref(false), requirementDialogVisible = ref(false), closeRequirementVisible = ref(false), taskDialogVisible = ref(false), closeTaskVisible = ref(false)
const caseDialogVisible = ref(false), runDialogVisible = ref(false), bugDialogVisible = ref(false), bugActionVisible = ref(false), caseExecutionVisible = ref(false), caseBugVisible = ref(false)
const editingIterationId = ref(null), startingIterationId = ref(null), editingRequirementId = ref(null), closingRequirementId = ref(null), editingTaskId = ref(null)
const closingTaskId = ref(null)
const editingCaseId = ref(null), editingRunId = ref(null), editingBugId = ref(null)
const actingBug = ref(null)
const bugActionType = ref('')
const selectedCase = ref(null)
const bugSourceCase = ref(null)
const caseExecutionHistory = ref([])

const tabs = [
  { key: 'overview', label: '概览' },
  { key: 'iterations', label: '迭代' },
  { key: 'requirements', label: '需求' },
  { key: 'tasks', label: '任务' },
  { key: 'tests', label: '测试' },
  { key: 'bugs', label: 'Bug' },
  { key: 'members', label: '成员' },
  { key: 'settings', label: '配置' }
]
const projectStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '进行中', value: 'active' },
  { label: '已挂起', value: 'paused' },
  { label: '已关闭', value: 'closed' }
]
const iterationStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '进行中', value: 'active' },
  { label: '已完成', value: 'finished' },
  { label: '已关闭', value: 'closed' }
]
const requirementStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '激活', value: 'active' },
  { label: '完成', value: 'done' },
  { label: '关闭', value: 'closed' }
]
const requirementPriorityOptions = [
  { label: '1', value: '1' },
  { label: '2', value: '2' },
  { label: '3', value: '3' },
  { label: '4', value: '4' },
  { label: '5', value: '5' }
]
const requirementCloseReasons = ['已完成', '重复', '延期', '不做', '设计如此']
const closeReasons = requirementCloseReasons
const requirementTypeOptions = ['功能', '接口', '性能', '安全', '体验', '改进', '其他']
const legacyRequirementPriorityValues = { high: '1', medium: '3', low: '5' }
const reviewStatusOptions = [
  { label: '无需评审', value: 'not_required' },
  { label: '待评审', value: 'pending' },
  { label: '已通过', value: 'approved' }
]
const taskStatusOptions = [
  { label: '待办', value: 'todo' },
  { label: '进行中', value: 'doing' },
  { label: '完成', value: 'done' },
  { label: '关闭', value: 'closed' }
]
const caseTypeOptions = [
  { label: '接口测试', value: 'api' },
  { label: '功能测试', value: 'functional' },
  { label: '安装部署', value: 'deploy' },
  { label: '配置相关', value: 'config' },
  { label: '性能测试', value: 'performance' },
  { label: '安全相关', value: 'security' },
  { label: '其他', value: 'other' }
]
const testScopeOptions = [
  { label: '单元测试环节', value: 'unit_test' },
  { label: '功能测试环节', value: 'functional_test' },
  { label: '集成测试环节', value: 'integration_test' },
  { label: '系统测试环节', value: 'system_test' },
  { label: '冒烟测试环节', value: 'smoke_test' },
  { label: '版本验证环节', value: 'release_verification' }
]
const executionResultOptions = [
  { label: '忽略', value: 'ignored' },
  { label: '通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '阻塞', value: 'blocked' }
]
const bugTypeOptions = ['代码错误', '配置相关', '安装部署', '安全相关', '性能问题', '标准规范', '测试脚本', '设计缺陷', '其他']
const priorityLevelOptions = [
  { label: '① 最高', value: '1' },
  { label: '② 高', value: '2' },
  { label: '③ 中', value: '3' },
  { label: '④ 低', value: '4' },
  { label: '⑤ 最低', value: '5' }
]
const testRunStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '执行中', value: 'running' },
  { label: '完成', value: 'finished' }
]
const projectMemberRoleOptions = [
  { label: '?????', value: 'product_owner' },
  { label: '?????', value: 'tech_lead' },
  { label: '??', value: 'developer' },
  { label: '?????', value: 'test_lead' },
  { label: '??', value: 'tester' },
  { label: '???', value: 'viewer' }
]
const bugStatusOptions = [
  { label: '待确认', value: 'open' },
  { label: '修复中', value: 'fixing' },
  { label: '已解决', value: 'resolved' },
  { label: '待验证', value: 'verifying' },
  { label: '已关闭', value: 'closed' },
  { label: '重新打开', value: 'reopened' },
  { label: '已挂起', value: 'suspended' }
]
const bugResolutionOptions = [
  { label: '设计如此', value: '设计如此' },
  { label: '重复Bug', value: '重复Bug' },
  { label: '外部原因', value: '外部原因' },
  { label: '已解决', value: '已解决' },
  { label: '无法重现', value: '无法重现' },
  { label: '延期处理', value: '延期处理' },
  { label: '不予解决', value: '不予解决' }
]

const projectIterations = computed(() => projectIterationRows.value)
const projectRequirements = computed(() => projectRequirementRows.value)
const projectTasks = computed(() => projectTaskRows.value)
const projectClosed = computed(() => project.value.status === 'closed')
const projectTestCases = computed(() => projectTestCaseRows.value)
const projectTestRuns = computed(() => projectTestRunRows.value)
const projectBugs = computed(() => projectBugRows.value)
const pagedProjectIterations = computed(() => projectIterations.value)
const pagedProjectRequirements = computed(() => projectRequirements.value)
const pagedProjectTasks = computed(() => projectTasks.value)
const pagedProjectTestCases = computed(() => projectTestCases.value)
const pagedProjectTestRuns = computed(() => projectTestRuns.value)
const pagedProjectBugs = computed(() => projectBugs.value)
const projectIterationOptions = computed(() => iterations.value.filter((item) => (item.project_ids || []).includes(projectId.value)))
const projectRequirementOptions = computed(() => requirements.value.filter((item) => item.project_id === projectId.value))
const projectTaskOptions = computed(() => tasks.value.filter((item) => item.project_id === projectId.value))
const projectTestCaseOptions = computed(() => testCases.value.filter((item) => item.project_id === projectId.value))
const projectTestRunOptions = computed(() => testRuns.value.filter((item) => item.project_id === projectId.value))
const activeTabLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label || '')
const projectEndDateLabel = computed(() => project.value.is_long_term ? '长期' : project.value.end_date || '未设置结束')
const metrics = computed(() => [
  { key: 'iterations', label: '迭代', value: projectListTotals.iterations },
  { key: 'requirements', label: '需求', value: projectListTotals.requirements },
  { key: 'tasks', label: '任务', value: projectListTotals.tasks },
  { key: 'tests', label: '测试', value: projectListTotals.testCases + projectListTotals.testRuns },
  { key: 'bugs', label: 'Bug', value: projectListTotals.bugs }
])
const projectHistory = computed(() => {
  const statusItems = projectStatusOperations.value.map((item) => ({
    key: `status-${item.id}`,
    type: 'status',
    time: item.effective_time || item.create_time,
    actor: item.actor_name || '系统',
    actionLabel: `${operationActionLabel(item.action)}`,
    changes: []
  }))
  const auditItems = projectAuditLogs.value.map((item) => ({
    key: `audit-${item.id}`,
    type: 'audit',
    time: item.create_time,
    actor: '系统',
    actionLabel: '编辑',
    changes: Object.keys(item.after_data || {}).map((field) => ({
      field,
      oldValue: item.before_data?.[field],
      newValue: item.after_data?.[field]
    }))
  }))
  return [...statusItems, ...auditItems].sort((a, b) => new Date(a.time) - new Date(b.time))
})

const failedExecutionCount = computed(() => caseExecutionHistory.value.filter((item) => item.result === 'failed').length)
const bugActionTitle = computed(() => ({
  start_fixing: '确认 Bug',
  resolve: '解决 Bug',
  activate: '激活 Bug',
  suspend: '挂起 Bug',
  close: '关闭 Bug'
}[bugActionType.value] || 'Bug 操作'))

const iterationForm = reactive({ project_ids: [], name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' })
const iterationStartForm = reactive({ effective_time: '', remark: '' })
const iterationFinishForm = reactive({ effective_time: '', remark: '' })
const requirementForm = reactive({ project_id: null, iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: null, status: 'draft', review_status: 'not_required', description: '', acceptance_criteria: '', source_reviewed: false })
const closeRequirementForm = reactive({ reason: '', remark: '' })
const taskForm = reactive({ project_id: null, requirement_id: null, title: '', task_type: '', priority: 'medium', owner_id: null, estimated_hours: null, actual_hours: null, due_date: null, status: 'todo', description: '' })
const closeTaskForm = reactive({ reason: '', remark: '' })
const caseForm = reactive({ project_id: null, requirement_id: null, title: '', case_type: 'functional', test_scope: 'functional_test', default_tester_id: defaultProjectMember(['tester', 'test_lead']), precondition: '', steps_json: [{ step: '', expected: '' }], expected_result: '' })
const caseExecutionForm = reactive({ execute_time: '', steps_result_json: [] })
const runForm = reactive({ project_id: null, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' })
const bugForm = reactive({ project_id: null, iteration_id: null, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', bug_type: '代码错误', severity: '3', priority: '3', owner_id: defaultProjectMember(['developer', 'tech_lead']), reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '', status: 'open' })
const bugActionForm = reactive({ resolution: '', verify_result: '', iteration_id: null, reason: '', remark: '' })
const caseBugForm = reactive({ title: '', bug_type: '代码错误', severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function normalizeProjectTab(value) {
  return ['overview', 'iterations', 'requirements', 'tasks', 'tests', 'bugs', 'members', 'settings'].includes(value) ? value : 'overview'
}
function setActiveTab(key) {
  activeTab.value = key
  router.replace({ name: 'project-detail', params: { id: projectId.value }, query: { ...route.query, tab: key } })
}
function projectListParams(key) {
  const pager = projectListPagination[key]
  const keyword = projectListFilters[key]?.keyword?.trim()
  return {
    page: pager.currentPage,
    page_size: pager.pageSize,
    keyword: keyword || undefined
  }
}
function applyProjectPage(key, response, targetRef) {
  const data = response.data
  targetRef.value = data.items || []
  projectListTotals[key] = data.total || 0
  const pager = projectListPagination[key]
  const maxPage = Math.max(1, Math.ceil(projectListTotals[key] / pager.pageSize))
  if (pager.currentPage > maxPage) {
    pager.currentPage = maxPage
    return true
  }
  return false
}
async function loadProjectIterationsPage() {
  if (applyProjectPage('iterations', await fetchProjectIterations(projectId.value, projectListParams('iterations')), projectIterationRows)) await loadProjectIterationsPage()
}
async function loadProjectRequirementsPage() {
  if (applyProjectPage('requirements', await fetchProjectRequirements(projectId.value, projectListParams('requirements')), projectRequirementRows)) return loadProjectRequirementsPage()
  closeReasonByRequirement.value = await loadCloseReasonMap(projectRequirements.value, fetchRequirementStatusOperations)
}
async function loadProjectTasksPage() {
  if (applyProjectPage('tasks', await fetchProjectTasks(projectId.value, projectListParams('tasks')), projectTaskRows)) return loadProjectTasksPage()
  closeReasonByTask.value = await loadCloseReasonMap(projectTasks.value, fetchTaskStatusOperations)
}
async function loadProjectTestCasesPage() {
  if (applyProjectPage('testCases', await fetchProjectTestCases(projectId.value, projectListParams('testCases')), projectTestCaseRows)) await loadProjectTestCasesPage()
}
async function loadProjectTestRunsPage() {
  if (applyProjectPage('testRuns', await fetchProjectTestRuns(projectId.value, projectListParams('testRuns')), projectTestRunRows)) await loadProjectTestRunsPage()
}
async function loadProjectBugsPage() {
  if (applyProjectPage('bugs', await fetchProjectBugs(projectId.value, projectListParams('bugs')), projectBugRows)) await loadProjectBugsPage()
}
async function loadProjectListPage(key) {
  const loaders = {
    iterations: loadProjectIterationsPage,
    requirements: loadProjectRequirementsPage,
    tasks: loadProjectTasksPage,
    testCases: loadProjectTestCasesPage,
    testRuns: loadProjectTestRunsPage,
    bugs: loadProjectBugsPage
  }
  await loaders[key]()
}
async function refreshActiveProjectList() {
  if (activeTab.value === 'iterations') return loadProjectIterationsPage()
  if (activeTab.value === 'requirements') return loadProjectRequirementsPage()
  if (activeTab.value === 'tasks') return loadProjectTasksPage()
  if (activeTab.value === 'bugs') return loadProjectBugsPage()
  if (activeTab.value === 'tests') {
    return testTab.value === 'runs' ? loadProjectTestRunsPage() : loadProjectTestCasesPage()
  }
  return Promise.resolve()
}
function resetProjectListSearch(key) {
  const pager = projectListPagination[key]
  pager.currentPage = 1
  loadProjectListPage(key)
}
function projectStatusLabel(value) { return optionLabel(projectStatusOptions, value) }
function iterationStatusLabel(value) { return optionLabel(iterationStatusOptions, value) }
function normalizeRequirementPriority(value) { return legacyRequirementPriorityValues[value] || value || '3' }
function requirementStatusLabel(value) { return optionLabel(requirementStatusOptions, value) }
function reviewStatusLabel(value) { return optionLabel(reviewStatusOptions, value) }
function taskStatusLabel(value) { return optionLabel(taskStatusOptions, value) }
function testRunStatusLabel(value) { return optionLabel(testRunStatusOptions, value) }
function bugStatusLabel(value) { return optionLabel(bugStatusOptions, value) }
function operationActionLabel(value) { return optionLabel([{ label: '启动', value: 'start' }, { label: '挂起', value: 'suspend' }, { label: '关闭', value: 'close' }, { label: '激活', value: 'activate' }], value) }
function canActivateRequirement(row) { return ['draft', 'closed'].includes(row.status) }
function canActivateTask(row) { return ['todo', 'closed'].includes(row.status) }
function apiErrorMessage(error, fallback) { return error?.response?.data?.detail || fallback }
function showActionError(error, fallback) { ElMessageBox.alert(apiErrorMessage(error, fallback), '提示', { type: 'warning' }) }
function isHistoryExpanded(key) {
  return expandedHistoryKeys.value.has(key)
}
function toggleHistory(key) {
  const next = new Set(expandedHistoryKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedHistoryKeys.value = next
}
function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function executionResultLabel(value) { return executionResultOptions.find((option) => option.value === value)?.label || '-' }
function canCreateBugFromCase(row) { return ['failed', 'blocked'].includes(row.last_execute_result) }
function executionHistoryTitle(item) { return `#${item.id} ${formatDateTime(item.execute_time)}，结果为 ${executionResultLabel(item.result)}` }
function defaultExecutionTime() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
function currentDateTimeValue() { return defaultExecutionTime() }
function displayHistoryValue(field, value) {
  return formatAuditValue(field, value, {
    users: users.value,
    projects: projects.value,
    programs: programs.value,
    iterations: projectIterationOptions.value,
    requirements: projectRequirementOptions.value,
    tasks: projectTaskOptions.value,
    testCases: projectTestCaseOptions.value,
    testRuns: projectTestRunOptions.value
  })
}
function projectFieldLabel(field) {
  return optionLabel([
    { label: '项目名称', value: 'name' },
    { label: '上级项目', value: 'parent_id' },
    { label: '所属项目集', value: 'program_id' },
    { label: '负责人', value: 'owner_id' },
    { label: '计划开始', value: 'start_date' },
    { label: '计划结束', value: 'end_date' },
    { label: '实际开始', value: 'actual_start_date' },
    { label: '实际结束', value: 'actual_end_date' },
    { label: '长期', value: 'is_long_term' },
    { label: '描述', value: 'description' },
    { label: '工作流配置', value: 'workflow_config_id' }
  ], field)
}
function defaultProjectMember(roles) {
  const candidates = projectMembers.value.filter((item) => roles.includes(item.project_role) && item.user_id)
  return (candidates.find((item) => item.is_default_assignee) || candidates[0])?.user_id || null
}
function addProjectMember() {
  projectMembers.value.push({
    user_id: null,
    project_role: 'developer',
    is_default_assignee: false,
    is_workbench_participant: true,
    sort_order: projectMembers.value.length
  })
}
function removeProjectMember(index) {
  projectMembers.value.splice(index, 1)
}
async function submitProjectMembers() {
  const payload = projectMembers.value
    .filter((item) => item.user_id && item.project_role)
    .map((item, index) => ({
      user_id: item.user_id,
      project_role: item.project_role,
      is_default_assignee: Boolean(item.is_default_assignee),
      is_workbench_participant: item.is_workbench_participant !== false,
      sort_order: item.sort_order ?? index
    }))
  saving.value = true
  try {
    projectMembers.value = (await saveProjectMembers(projectId.value, payload)).data
    ElMessage.success('项目成员已保存')
  } finally {
    saving.value = false
  }
}
function resetIterationForm() { Object.assign(iterationForm, { project_ids: [projectId.value], name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' }) }
function resetRequirementForm() { Object.assign(requirementForm, { project_id: projectId.value, iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: defaultProjectMember(['product_owner']), proposer_id: currentUserId(users.value), status: 'draft', review_status: 'not_required', description: '', acceptance_criteria: '', source_reviewed: false }) }
function resetTaskForm() { Object.assign(taskForm, { project_id: projectId.value, requirement_id: null, title: '', task_type: '', priority: 'medium', owner_id: defaultProjectMember(['developer', 'tech_lead']), estimated_hours: null, actual_hours: null, due_date: null, status: 'todo', description: '' }) }
function resetCaseForm() { Object.assign(caseForm, { project_id: projectId.value, requirement_id: null, title: '', case_type: 'functional', test_scope: 'functional_test', default_tester_id: defaultProjectMember(['tester', 'test_lead']), precondition: '', steps_json: [{ step: '', expected: '' }], expected_result: '' }) }
function resetRunForm() { Object.assign(runForm, { project_id: projectId.value, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' }) }
function resetBugForm() { Object.assign(bugForm, { project_id: projectId.value, iteration_id: null, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', bug_type: '代码错误', severity: '3', priority: '3', owner_id: defaultProjectMember(['developer', 'tech_lead']), reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '', status: 'open' }) }

function openIterationCreate() { editingIterationId.value = null; resetIterationForm(); iterationDialogVisible.value = true }
function openIterationEdit(row) { editingIterationId.value = row.id; Object.assign(iterationForm, { ...row, project_ids: row.project_ids || [], goal: row.goal || '' }); iterationDialogVisible.value = true }
function openIterationStart(row) { startingIterationId.value = row.id; Object.assign(iterationStartForm, { effective_time: currentDateTimeValue(), remark: '' }); iterationStartVisible.value = true }
function openIterationFinish(row) { startingIterationId.value = row.id; Object.assign(iterationFinishForm, { effective_time: currentDateTimeValue(), remark: '' }); iterationFinishVisible.value = true }
function openRequirementCreate() { editingRequirementId.value = null; resetRequirementForm(); requirementDialogVisible.value = true }
function openRequirementEdit(row) { editingRequirementId.value = row.id; Object.assign(requirementForm, { ...row, priority: normalizeRequirementPriority(row.priority), requirement_type: row.requirement_type || '', description: row.description || '', acceptance_criteria: row.acceptance_criteria || '' }); requirementDialogVisible.value = true }
function openGenerate(row) { editingTaskId.value = null; resetTaskForm(); Object.assign(taskForm, { requirement_id: row.id, title: row.title, owner_id: taskOwnerForRequirement(row) }); taskDialogVisible.value = true }
function openRequirementClose(row) { closingRequirementId.value = row.id; Object.assign(closeRequirementForm, { reason: '', remark: '' }); closeRequirementVisible.value = true }
function openTaskCreate() { editingTaskId.value = null; resetTaskForm(); taskDialogVisible.value = true }
function openTaskEdit(row) { editingTaskId.value = row.id; Object.assign(taskForm, { ...row, task_type: row.task_type || '', description: row.description || '' }); taskDialogVisible.value = true }
function openTaskClose(row) { closingTaskId.value = row.id; Object.assign(closeTaskForm, { reason: '', remark: '' }); closeTaskVisible.value = true }
function taskOwnerForRequirement(requirement) { return requirement?.owner_id || defaultProjectMember(['developer', 'tech_lead']) || null }
function onTaskRequirementChange(requirementId) {
  const requirement = projectRequirementOptions.value.find((item) => item.id === requirementId)
  taskForm.owner_id = requirement?.owner_id || defaultProjectMember(['developer', 'tech_lead']) || null
}
function openCaseCreate() { editingCaseId.value = null; resetCaseForm(); caseDialogVisible.value = true }
function openCaseCreateForRequirement(row) { editingCaseId.value = null; resetCaseForm(); Object.assign(caseForm, { requirement_id: row.id, title: row.title }); caseDialogVisible.value = true }
function openCaseEdit(row) { editingCaseId.value = row.id; Object.assign(caseForm, { ...row, case_type: row.case_type || 'functional', test_scope: row.test_scope || 'functional_test', precondition: row.precondition || '', steps_json: normalizeCaseSteps(row.steps_json), expected_result: row.expected_result || '' }); caseDialogVisible.value = true }
async function openCaseExecution(row) {
  selectedCase.value = row
  Object.assign(caseExecutionForm, {
    execute_time: defaultExecutionTime(),
    steps_result_json: normalizeCaseSteps(row.steps_json).map((item) => ({ ...item, result: 'passed', actual: '' }))
  })
  caseExecutionHistory.value = (await fetchTestCaseExecutions(row.id)).data
  caseExecutionVisible.value = true
}
async function openCaseBug(row) {
  if (!canCreateBugFromCase(row)) return
  bugSourceCase.value = row
  const history = (await fetchTestCaseExecutions(row.id)).data
  const latest = history[0]
  Object.assign(caseBugForm, {
    title: row.title,
    bug_type: '代码错误',
    severity: '3',
    priority: '3',
    reproduce_steps: buildReproduceText(latest, row),
    actual_result: buildActualText(latest)
  })
  caseBugVisible.value = true
}
function normalizeCaseSteps(value) { return Array.isArray(value) && value.length ? value.map((item) => ({ step: item.step || '', expected: item.expected || '' })) : [{ step: '', expected: '' }] }
function addCaseStep() { caseForm.steps_json.push({ step: '', expected: '' }) }
function removeCaseStep(index) { if (caseForm.steps_json.length > 1) caseForm.steps_json.splice(index, 1) }
function cleanCaseSteps() { return caseForm.steps_json.filter((item) => item.step.trim() || item.expected.trim()) }
function openRunCreate() { editingRunId.value = null; resetRunForm(); runDialogVisible.value = true }
function openRunEdit(row) { editingRunId.value = row.id; Object.assign(runForm, { ...row, remark: row.remark || '' }); runDialogVisible.value = true }
function openBugCreate() { editingBugId.value = null; resetBugForm(); bugDialogVisible.value = true }
function openBugEdit(row) { editingBugId.value = row.id; Object.assign(bugForm, { ...row, reproduce_steps: row.reproduce_steps || '', expected_result: row.expected_result || '', actual_result: row.actual_result || '' }); bugDialogVisible.value = true }
function openBugAction(row, actionType) {
  actingBug.value = row
  bugActionType.value = actionType
  Object.assign(bugActionForm, {
    resolution: actionType === 'resolve' ? '已解决' : '',
    verify_result: actionType === 'close' ? 'passed' : actionType === 'activate' ? 'failed' : '',
    iteration_id: actionType === 'start_fixing' ? row.iteration_id || null : null,
    reason: '',
    remark: ''
  })
  bugActionVisible.value = true
}

async function safeFetchProjectMembers(id) {
  try {
    return await fetchProjectMembers(id)
  } catch (error) {
    console.warn('Failed to load project members, fallback to empty list.', error)
    return { data: [] }
  }
}

async function loadData() {
  loading.value = true
  try {
    const [
      projectRes,
      projectsRes,
      programRes,
      userRes,
      iterationRefRes,
      requirementRefRes,
      taskRefRes,
      memberRes,
      auditRes,
      statusRes,
      iterationRes,
      requirementRes,
      taskRes,
      caseRes,
      runRes,
      bugRes
    ] = await Promise.all([
      fetchProject(projectId.value),
      fetchProjects(),
      fetchPrograms(),
      fetchUsers(),
      fetchIterations({ project_id: projectId.value }),
      fetchRequirements(),
      fetchTasks(),
      safeFetchProjectMembers(projectId.value),
      fetchProjectAuditLogs(projectId.value),
      fetchProjectStatusOperations(projectId.value),
      fetchProjectIterations(projectId.value, projectListParams('iterations')),
      fetchProjectRequirements(projectId.value, projectListParams('requirements')),
      fetchProjectTasks(projectId.value, projectListParams('tasks')),
      fetchProjectTestCases(projectId.value, projectListParams('testCases')),
      fetchProjectTestRuns(projectId.value, projectListParams('testRuns')),
      fetchProjectBugs(projectId.value, projectListParams('bugs'))
    ])
    project.value = projectRes.data
    projects.value = projectsRes.data
    programs.value = programRes.data; users.value = userRes.data
    iterations.value = iterationRefRes.data; requirements.value = requirementRefRes.data; tasks.value = taskRefRes.data
    projectMembers.value = memberRes.data
    applyProjectPage('iterations', iterationRes, projectIterationRows)
    applyProjectPage('requirements', requirementRes, projectRequirementRows)
    applyProjectPage('tasks', taskRes, projectTaskRows)
    applyProjectPage('testCases', caseRes, projectTestCaseRows)
    applyProjectPage('testRuns', runRes, projectTestRunRows)
    applyProjectPage('bugs', bugRes, projectBugRows)
    projectAuditLogs.value = auditRes.data; projectStatusOperations.value = statusRes.data
    closeReasonByRequirement.value = await loadCloseReasonMap(projectRequirements.value, fetchRequirementStatusOperations)
    closeReasonByTask.value = await loadCloseReasonMap(projectTasks.value, fetchTaskStatusOperations)
  } catch {
    ElMessage.error('项目详情加载失败')
  } finally {
    loading.value = false
  }
}

async function refreshProjectReferences() {
  const [iterationRefRes, requirementRefRes, taskRefRes] = await Promise.all([
    fetchIterations({ project_id: projectId.value }),
    fetchRequirements(),
    fetchTasks()
  ])
  iterations.value = iterationRefRes.data
  requirements.value = requirementRefRes.data
  tasks.value = taskRefRes.data
}

async function refreshAfterMutation() {
  await refreshProjectReferences()
  await refreshActiveProjectList()
}

async function submitIteration() { if (!iterationForm.name.trim()) return ElMessage.warning('请填写迭代名称'); saving.value = true; try { const payload = { ...iterationForm, project_ids: iterationForm.project_ids.length ? iterationForm.project_ids : [projectId.value], owner_id: iterationForm.owner_id || null }; if (editingIterationId.value) await updateIteration(editingIterationId.value, payload); else await createIteration(payload); iterationDialogVisible.value = false; await refreshAfterMutation() } finally { saving.value = false } }
async function submitIterationStart() { if (!iterationStartForm.effective_time) return ElMessage.warning('请选择实际开始日期'); saving.value = true; try { await startIteration(startingIterationId.value, { ...iterationStartForm }); iterationStartVisible.value = false; await refreshAfterMutation(); ElMessage.success('迭代已开始') } finally { saving.value = false } }
async function submitIterationFinish() { if (!iterationFinishForm.effective_time) return ElMessage.warning('请选择实际结束日期'); saving.value = true; try { await finishIteration(startingIterationId.value, { ...iterationFinishForm }); iterationFinishVisible.value = false; await refreshAfterMutation(); ElMessage.success('迭代已结束') } finally { saving.value = false } }
async function submitRequirement() { if (!requirementForm.title.trim()) return ElMessage.warning('请填写需求标题'); saving.value = true; try { const { status: _status, ...formData } = requirementForm; const payload = { ...formData, project_id: projectId.value, iteration_id: requirementForm.iteration_id || null, owner_id: requirementForm.owner_id || null, proposer_id: requirementForm.proposer_id || null }; if (editingRequirementId.value) await updateRequirement(editingRequirementId.value, payload); else await createRequirement(payload); requirementDialogVisible.value = false; await refreshAfterMutation() } finally { saving.value = false } }
async function activateRequirementRow(id) { try { await activateRequirement(id); await refreshAfterMutation(); ElMessage.success('需求已激活，关联任务已进入进行中') } catch (error) { showActionError(error, '需求激活失败') } }
async function submitRequirementClose() {
  if (!closeRequirementForm.reason) return ElMessage.warning('请选择关闭原因')
  saving.value = true
  try {
    await closeRequirement(closingRequirementId.value, { ...closeRequirementForm })
    closeRequirementVisible.value = false
    await refreshAfterMutation()
    ElMessage.success('需求已关闭')
  } finally {
    saving.value = false
  }
}
async function submitTask() { if (!taskForm.title.trim()) return ElMessage.warning('请填写任务标题'); saving.value = true; try { const payload = { ...taskForm, project_id: projectId.value, requirement_id: taskForm.requirement_id || null, owner_id: taskForm.owner_id || null }; if (editingTaskId.value) await updateTask(editingTaskId.value, payload); else await createTask(payload); taskDialogVisible.value = false; await refreshAfterMutation() } finally { saving.value = false } }
async function activateTaskRow(id) { try { await activateTask(id); await refreshAfterMutation(); ElMessage.success('任务已激活') } catch (error) { showActionError(error, '任务激活失败') } }
async function submitTaskClose() { if (!closeTaskForm.reason) return ElMessage.warning('请选择关闭原因'); saving.value = true; try { await closeTask(closingTaskId.value, { ...closeTaskForm }); closeTaskVisible.value = false; await refreshAfterMutation(); ElMessage.success('任务已关闭') } catch (error) { showActionError(error, '任务关闭失败') } finally { saving.value = false } }
async function submitCase() { if (!caseForm.title.trim()) return ElMessage.warning('请填写用例标题'); saving.value = true; try { const payload = { ...caseForm, project_id: projectId.value, requirement_id: caseForm.requirement_id || null, default_tester_id: caseForm.default_tester_id || null, steps_json: cleanCaseSteps() }; if (editingCaseId.value) await updateTestCase(editingCaseId.value, payload); else await createTestCase(payload); caseDialogVisible.value = false; await refreshAfterMutation() } finally { saving.value = false } }
async function submitCaseExecution() { saving.value = true; try { const currentId = selectedCase.value.id; await executeTestCase(currentId, { execute_time: caseExecutionForm.execute_time, steps_result_json: caseExecutionForm.steps_result_json }); await refreshAfterMutation(); ElMessage.success('用例执行结果已保存'); await openNextCaseAfterExecution(currentId, projectTestCases.value) } finally { saving.value = false } }
async function submitRun() { if (!runForm.name.trim()) return ElMessage.warning('请填写测试单名称'); saving.value = true; try { const payload = { ...runForm, project_id: projectId.value, iteration_id: runForm.iteration_id || null, test_owner_id: runForm.test_owner_id || null }; if (editingRunId.value) await updateTestRun(editingRunId.value, payload); else await createTestRun(payload); runDialogVisible.value = false; await refreshAfterMutation() } finally { saving.value = false } }
async function submitBug() { if (!bugForm.title.trim()) return ElMessage.warning('请填写 Bug 标题'); saving.value = true; try { const payload = { ...bugForm, project_id: projectId.value, iteration_id: bugForm.iteration_id || null, requirement_id: bugForm.requirement_id || null, task_id: bugForm.task_id || null, test_case_id: bugForm.test_case_id || null, test_run_id: bugForm.test_run_id || null, owner_id: bugForm.owner_id || null, reporter_id: bugForm.reporter_id || null }; if (editingBugId.value) await updateBug(editingBugId.value, payload); else await createBug(payload); bugDialogVisible.value = false; await refreshAfterMutation() } finally { saving.value = false } }
async function submitBugAction() {
  if (bugActionType.value === 'resolve' && !bugActionForm.resolution) return ElMessage.warning('请选择解决结果')
  saving.value = true
  try {
    const id = actingBug.value.id
    const payload = ['activate', 'close'].includes(bugActionType.value) ? { remark: bugActionForm.remark } : { ...bugActionForm }
    const actions = {
      start_fixing: startFixingBug,
      resolve: resolveBug,
      activate: activateBug,
      suspend: suspendBug,
      close: closeBug
    }
    await actions[bugActionType.value](id, payload)
    bugActionVisible.value = false
    await refreshAfterMutation()
    ElMessage.success('Bug 状态已更新')
  } finally {
    saving.value = false
  }
}
async function submitCaseBug() { if (!caseBugForm.title.trim()) return ElMessage.warning('请填写 Bug 标题'); saving.value = true; try { await createBugFromTestCase(bugSourceCase.value.id, { ...caseBugForm }); caseBugVisible.value = false; await refreshAfterMutation(); ElMessage.success('Bug 已提交') } finally { saving.value = false } }
async function removeIteration(id) { await deleteIteration(id); await refreshAfterMutation() }
async function removeRequirement(id) { await deleteRequirement(id); await refreshAfterMutation() }
async function removeTask(id) { await deleteTask(id); await refreshAfterMutation() }
async function removeCase(id) { await deleteTestCase(id); await refreshAfterMutation() }
async function removeRun(id) { await deleteTestRun(id); await refreshAfterMutation() }
async function removeBug(id) { await deleteBug(id); await refreshAfterMutation() }

onMounted(loadData)
watch(() => route.query.tab, async (value) => {
  activeTab.value = normalizeProjectTab(value)
  await refreshActiveProjectList()
})
watch(testTab, async () => {
  if (activeTab.value === 'tests') await refreshActiveProjectList()
})

async function openNextCaseAfterExecution(currentId, rows) {
  const index = rows.findIndex((item) => item.id === currentId)
  const next = index >= 0 ? rows[index + 1] : null
  if (next) await openCaseExecution(next)
  else caseExecutionVisible.value = false
}
function buildReproduceText(execution, testCase) {
  const rows = Array.isArray(execution?.steps_result_json) ? execution.steps_result_json : []
  if (!rows.length) return testCase.expected_result || ''
  return [
    '[步骤]',
    ...rows.map((row, index) => `${index + 1}. ${row.step || ''}`),
    '',
    '[结果]',
    ...rows.map((row, index) => `${index + 1}. ${executionResultLabel(row.result)} ${row.actual || ''}`),
    '',
    '[期望]',
    ...rows.map((row, index) => `${index + 1}. ${row.expected || ''}`)
  ].join('\n')
}
function buildActualText(execution) {
  const rows = Array.isArray(execution?.steps_result_json) ? execution.steps_result_json : []
  return rows.map((row) => row.actual).filter(Boolean).join('\n')
}
</script>
