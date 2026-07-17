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
      <el-tag size="large">{{ project.status_name || '-' }}</el-tag>
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
          <el-descriptions-item label="状态">{{ project.status_name || '-' }}</el-descriptions-item>
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
          <el-button v-if="canManageCurrentProject" type="primary" @click="openIterationCreate">新增迭代</el-button>
        </div>
        <el-table :data="pagedProjectIterations" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="迭代名称" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <router-link class="table-link" :to="{ name: 'iteration-detail', params: { id: row.id }, query: { from: 'project', projectId, tab: 'iterations' } }">{{ row.name }}</router-link>
            </template>
          </el-table-column>
          <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column prop="start_date" label="开始日期" width="130" />
          <el-table-column prop="end_date" label="结束日期" width="130" />
          <el-table-column prop="actual_start_date" label="实际开始" width="130" />
          <el-table-column prop="actual_end_date" label="实际结束" width="130" />
          <el-table-column label="状态" width="120"><template #default="{ row }">{{ row.status_name || '-' }}</template></el-table-column>
          <el-table-column label="操作" width="250" fixed="right">
            <template #default="{ row }"><WorkflowActionButtons v-if="canManageCurrentProject" object-type="iteration" :object-id="row.id" mode="list" :transitions="projectWorkflowTransitionsFor('iteration', row.id)" :auto-load="false" :users="users" @executed="refreshAfterMutation" /><el-button v-if="canManageCurrentProject && iterationCanDefer(row)" link type="warning" @click="openDeferWorkItems(row)">延期工作项</el-button><el-button v-if="canManageCurrentProject" link type="primary" @click="openIterationEdit(row)">编辑</el-button><el-popconfirm v-if="canManageCurrentProject" title="确认删除该迭代？" @confirm="removeIteration(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
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
          <el-button v-if="canCreateCurrentWorkItem && !projectClosed" @click="openImportDialog">导入需求</el-button>
          <el-button v-if="canCreateCurrentWorkItem && !projectClosed" type="primary" @click="openRequirementCreate">新增需求</el-button>
        </div>
        <el-table :data="pagedProjectRequirements" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="需求标题" min-width="180" show-overflow-tooltip>
            <template #default="{ row }"><router-link class="table-link" :to="`/requirements/${row.id}`">{{ row.title }}</router-link></template>
          </el-table-column>
          <el-table-column label="迭代" width="140"><template #default="{ row }">{{ labelById(requirementIterationDisplayOptions, row.iteration_id) }}</template></el-table-column>
          <el-table-column label="当前处理人" width="130"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column label="优先级" width="100"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tooltip v-if="closeReasonByRequirement[row.id]" :content="closeReasonByRequirement[row.id]" placement="top" raw-content>
                <span class="status-with-reason">{{ row.status_name || '-' }}</span>
              </el-tooltip>
              <span v-else>{{ row.status_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="360" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
              <el-button v-if="canEditWorkItem(row)" link type="primary" @click="openRequirementEdit(row)">编辑</el-button>
              <WorkflowActionButtons
                object-type="requirement"
                :object-id="row.id"
                mode="list"
                :transitions="projectWorkflowTransitionsFor('requirement', row.id)"
                :auto-load="false"
                :users="users"
                @executed="refreshAfterMutation"
              />
              <el-button v-if="canCreateCurrentWorkItem && !projectClosed" link type="success" @click="openGenerate(row)">生成任务</el-button>
              <el-button v-if="canManageCurrentTestCase && !projectClosed" link type="success" @click="openCaseCreateForRequirement(row)">建用例</el-button>
              <el-popconfirm v-if="canDeleteCurrentWorkItem && !projectClosed" title="确认删除该需求？" @confirm="removeRequirement(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
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
          <el-button v-if="canCreateCurrentWorkItem && !projectClosed" type="primary" @click="openTaskCreate">新增任务</el-button>
        </div>
        <el-table :data="pagedProjectTasks" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="任务标题" min-width="180" show-overflow-tooltip>
            <template #default="{ row }"><router-link class="table-link" :to="`/tasks/${row.id}`">{{ row.title }}</router-link></template>
          </el-table-column>
          <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(projectRequirementOptions, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column label="任务分支" width="120"><template #default="{ row }">{{ taskBranchLabel(row.task_type) }}</template></el-table-column>
          <el-table-column label="当前处理人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column prop="due_date" label="截止日期" width="130" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tooltip v-if="closeReasonByTask[row.id]" :content="closeReasonByTask[row.id]" placement="top" raw-content>
                <span class="status-with-reason">{{ row.status_name || '-' }}</span>
              </el-tooltip>
              <span v-else>{{ row.status_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }"><el-button v-if="canEditWorkItem(row)" link type="primary" @click="openTaskEdit(row)">编辑</el-button><WorkflowActionButtons object-type="task" :object-id="row.id" mode="list" :transitions="projectWorkflowTransitionsFor('task', row.id)" :auto-load="false" :users="users" @executed="refreshAfterMutation" /><el-popconfirm v-if="canDeleteCurrentWorkItem && !projectClosed" title="确认删除该任务？" @confirm="removeTask(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
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
              <el-button v-if="canManageCurrentTestCase" type="primary" @click="openCaseCreate">新增用例</el-button>
            </div>
            <el-table :data="pagedProjectTestCases" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column label="用例标题" min-width="180" show-overflow-tooltip><template #default="{ row }"><router-link class="table-link" :to="{ name: 'test-case-detail', params: { id: row.id }, query: { from: 'project' } }">{{ row.title }}</router-link></template></el-table-column>
              <el-table-column label="需求" width="180"><template #default="{ row }">{{ testCaseRequirementLabel(row.requirement_id) }}</template></el-table-column>
              <el-table-column label="测试人" width="140"><template #default="{ row }">{{ userLabel(users, row.default_tester_id) }}</template></el-table-column>
              <el-table-column label="最近执行时间" width="170"><template #default="{ row }">{{ formatDateTime(row.last_execute_time) }}</template></el-table-column>
              <el-table-column label="最近结果" width="110"><template #default="{ row }">{{ executionResultLabel(row.last_execute_result) }}</template></el-table-column>
              <el-table-column label="操作" width="280" fixed="right"><template #default="{ row }"><el-button v-if="canManageCurrentTestCase" link type="success" @click="openCaseExecution(row)">执行</el-button><el-button v-if="canManageCurrentTestCase" link type="warning" :disabled="!canCreateBugFromCase(row)" @click="openCaseBug(row)">提 Bug</el-button><el-button v-if="canManageCurrentTestCase" link type="primary" @click="openCaseEdit(row)">编辑</el-button><el-popconfirm v-if="canManageCurrentTestCase" title="确认删除该用例？" @confirm="removeCase(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template></el-table-column>
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
              <el-button v-if="canManageCurrentTestCase" type="primary" @click="openRunCreate">新增测试单</el-button>
            </div>
            <el-table :data="pagedProjectTestRuns" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="测试单名称" min-width="180" show-overflow-tooltip />
              <el-table-column label="迭代" width="160"><template #default="{ row }">{{ labelById(projectIterationOptions, row.iteration_id) }}</template></el-table-column>
              <el-table-column label="测试人" width="140"><template #default="{ row }">{{ userLabel(users, row.test_owner_id) }}</template></el-table-column>
              <el-table-column label="状态" width="110"><template #default="{ row }">{{ testRunStatusLabel(row.status) }}</template></el-table-column>
              <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button v-if="canManageCurrentTestCase" link type="primary" @click="openRunEdit(row)">编辑</el-button><el-popconfirm v-if="canManageCurrentTestCase" title="确认删除该测试单？" @confirm="removeRun(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template></el-table-column>
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
          <el-button v-if="canCreateCurrentWorkItem" type="primary" @click="openBugCreate">新增 Bug</el-button>
        </div>
        <el-table :data="pagedProjectBugs" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="Bug 标题" min-width="180" show-overflow-tooltip><template #default="{ row }"><router-link class="table-link" :to="{ name: 'bug-detail', params: { id: row.id }, query: { from: 'project' } }">{{ row.title }}</router-link></template></el-table-column>
          <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(projectRequirementOptions, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column label="任务" width="180"><template #default="{ row }">{{ labelById(projectTaskOptions, row.task_id, 'title') }}</template></el-table-column>
              <el-table-column label="当前处理人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column label="Bug 类型" width="120"><template #default="{ row }">{{ row.bug_type || '-' }}</template></el-table-column>
          <el-table-column label="严重程度" width="110"><template #default="{ row }"><RequirementPriorityBadge :value="row.severity" /></template></el-table-column>
          <el-table-column label="优先级" width="110"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
          <el-table-column label="状态" width="120"><template #default="{ row }">{{ row.status_name || '-' }}</template></el-table-column>
          <el-table-column label="操作" width="380" fixed="right">
            <template #default="{ row }">
              <div class="table-actions">
                <el-button v-if="canEditWorkItem(row)" link type="primary" @click="openBugEdit(row)">编辑</el-button>
                <WorkflowActionButtons
                  object-type="bug"
                  :object-id="row.id"
                  mode="list"
                  :transitions="projectWorkflowTransitionsFor('bug', row.id)"
                  :auto-load="false"
                  :users="users"
                  @executed="refreshAfterMutation"
                />
                <el-popconfirm v-if="canDeleteCurrentWorkItem" title="确认删除该 Bug？" @confirm="removeBug(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
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
          <el-button v-if="canManageCurrentProject" type="primary" @click="addProjectMember">添加成员</el-button>
          <el-button v-if="canManageCurrentProject" type="success" :loading="saving" @click="submitProjectMembers">保存成员</el-button>
        </div>
        <el-table :data="projectMembers" stripe width="100%">
          <el-table-column label="成员" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.user_id" clearable filterable :disabled="!canManageCurrentProject">
                <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="项目角色" min-width="180">
            <template #default="{ row }">
              <el-select v-model="row.project_role" :disabled="!canManageCurrentProject">
                <el-option v-for="option in projectMemberRoleOptions" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="纳入工作台" width="130" align="center">
            <template #default="{ row }">
              <el-tooltip content="该成员可在工作台按项目团队范围看到相关进行中工作项" placement="top">
                <el-checkbox v-model="row.is_workbench_participant" :disabled="!canManageCurrentProject" />
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="显示顺序" width="130">
            <template #default="{ row }"><el-input-number v-model="row.sort_order" :min="0" controls-position="right" :disabled="!canManageCurrentProject" /></template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ $index }"><el-button v-if="canManageCurrentProject" link type="danger" @click="removeProjectMember($index)">删除</el-button></template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else-if="activeTab === 'settings'">
        <div class="project-settings">
          <section class="project-settings-section">
            <div class="project-settings-head">
              <div>
                <h2>工作流方案</h2>
                <p>项目绑定一套工作流方案，需求、任务、Bug 会按方案内对应对象类型的流程执行。</p>
              </div>
              <el-tag type="info" effect="plain">{{ activeWorkflowSchemeLabel }}</el-tag>
            </div>
            <el-form label-position="top" class="project-settings-form">
              <el-form-item label="工作流方案">
                <el-select
                  v-model="settingsForm.assignee_rule_config_id"
                  clearable
                  filterable
                  :disabled="!canManageCurrentProject"
                  placeholder="请选择工作流方案"
                >
                  <el-option
                    v-for="scheme in enabledWorkflowSchemes"
                    :key="scheme.id"
                    :label="scheme.name"
                    :value="scheme.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="方案说明">
                <el-input
                  :model-value="selectedWorkflowSchemeDescription"
                  type="textarea"
                  :rows="3"
                  readonly
                  placeholder="选择工作流方案后显示说明"
                />
              </el-form-item>
              <el-alert
                title="切换方案不会批量修改已有工作项状态；后续新的状态流转和处理人流转按新方案执行。"
                type="info"
                :closable="false"
                show-icon
              />
            </el-form>
            <div v-if="canManageCurrentProject" class="project-settings-actions">
              <el-button @click="resetProjectSettings">重置</el-button>
              <el-button type="primary" :loading="saving" @click="submitProjectSettings">保存配置</el-button>
            </div>
          </section>
        </div>
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
        <div class="form-grid"><el-form-item label="负责人"><el-select v-model="iterationForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="开始日期"><el-date-picker v-model="iterationForm.start_date" value-format="YYYY-MM-DD" type="date" /></el-form-item><el-form-item label="结束日期"><el-date-picker v-model="iterationForm.end_date" value-format="YYYY-MM-DD" type="date" /></el-form-item></div>
        <el-form-item label="目标"><el-input v-model="iterationForm.goal" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="iterationDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitIteration">保存</el-button></template>
    </el-dialog>


    <el-dialog v-model="deferWorkItemsVisible" title="处理未完成项" width="720px">
      <el-alert
        title="当前迭代存在未完成需求或任务，请先延期到其他迭代后再结束当前迭代。"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-form label-position="top" class="defer-work-form">
        <el-form-item label="目标迭代" required>
          <el-select v-model="deferWorkItemsForm.target_iteration_id" filterable placeholder="请选择目标迭代">
            <el-option
              v-for="iteration in deferTargetIterations"
              :key="iteration.id"
              :label="iteration.name"
              :value="iteration.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="deferWorkItemsForm.remark" type="textarea" :rows="2" placeholder="例如：延期到下一迭代继续处理" />
        </el-form-item>
      </el-form>
      <div class="defer-work-lists">
        <div>
          <h3>未完成需求 {{ unfinishedIterationRequirements.length }}</h3>
          <el-table :data="unfinishedIterationRequirements" max-height="220" border>
            <el-table-column prop="title" label="标题" min-width="220" />
            <el-table-column label="状态" width="100"><template #default="{ row }">{{ row.status_name || '-' }}</template></el-table-column>
            <el-table-column label="当前处理人" width="120"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          </el-table>
        </div>
        <div>
          <h3>未完成任务 {{ unfinishedIterationTasks.length }}</h3>
          <el-table :data="unfinishedIterationTasks" max-height="220" border>
            <el-table-column prop="title" label="标题" min-width="220" />
            <el-table-column label="状态" width="100"><template #default="{ row }">{{ row.status_name || '-' }}</template></el-table-column>
            <el-table-column label="当前处理人" width="120"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <el-button @click="deferWorkItemsVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitDeferWorkItems">延期到目标迭代</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="requirementDialogVisible" :title="editingRequirementId ? '编辑需求' : '新增需求'" width="640px">
      <el-form label-position="top">
        <el-form-item label="需求标题" required><el-input v-model="requirementForm.title" /></el-form-item>
        <div class="form-grid"><el-form-item label="迭代"><el-select v-model="requirementForm.iteration_id" clearable filterable><el-option v-for="iteration in requirementIterationOptions" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item><el-form-item v-if="!editingRequirementId" label="当前处理人"><el-select v-model="requirementForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="提出人"><el-select v-model="requirementForm.proposer_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="类型"><el-select v-model="requirementForm.requirement_type"><el-option v-for="option in requirementTypeOptions" :key="option" :label="option" :value="option" /></el-select></el-form-item><el-form-item label="优先级"><el-select v-model="requirementForm.priority" class="priority-select"><template #prefix><RequirementPriorityBadge :value="requirementForm.priority" /></template><el-option v-for="option in requirementPriorityOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item></div>
        <el-form-item label="需求描述"><el-input v-model="requirementForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="requirementForm.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="requirementDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirement">保存</el-button></template>
    </el-dialog>

    

    <el-dialog v-model="taskDialogVisible" :title="editingTaskId ? '编辑任务' : '新增任务'" width="620px">
      <el-form label-position="top">
        <el-form-item label="任务标题" required><el-input v-model="taskForm.title" /></el-form-item>
        <div class="form-grid"><el-form-item label="需求"><el-select v-model="taskForm.requirement_id" clearable filterable @change="onTaskRequirementChange"><el-option v-for="requirement in projectRequirementOptions" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item><el-form-item label="任务分支"><el-select v-model="taskForm.task_type" :disabled="Boolean(taskForm.requirement_id)"><el-option v-for="option in TASK_BRANCH_OPTIONS" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item><el-form-item v-if="!editingTaskId" label="当前处理人"><el-select v-model="taskForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="优先级"><el-select v-model="taskForm.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item><el-form-item label="截止日期"><el-date-picker v-model="taskForm.due_date" value-format="YYYY-MM-DD" type="date" /></el-form-item></div>
        <el-form-item label="描述"><el-input v-model="taskForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="taskDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTask">保存</el-button></template>
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
          <el-form-item label="Bug 类型"><el-select v-model="caseBugForm.bug_type"><el-option v-for="option in bugTypeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
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
      <el-form label-position="top"><el-form-item label="Bug 标题" required><el-input v-model="bugForm.title" /></el-form-item><div class="form-grid"><el-form-item label="需求"><el-select v-model="bugForm.requirement_id" clearable filterable><el-option v-for="requirement in projectRequirementOptions" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item><el-form-item label="任务"><el-select v-model="bugForm.task_id" clearable filterable><el-option v-for="task in projectTaskOptions" :key="task.id" :label="task.title" :value="task.id" /></el-select></el-form-item><el-form-item label="来源用例"><el-select v-model="bugForm.test_case_id" clearable filterable><el-option v-for="item in projectTestCaseOptions" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item><el-form-item label="来源测试单"><el-select v-model="bugForm.test_run_id" clearable filterable><el-option v-for="run in projectTestRunOptions" :key="run.id" :label="run.name" :value="run.id" /></el-select></el-form-item><el-form-item label="所属迭代"><el-select v-model="bugForm.iteration_id" clearable filterable><el-option v-for="iteration in bugEditableIterationDisplayOptions" :key="iteration.id" :label="iteration.name" :value="iteration.id" :disabled="iteration.disabled" /></el-select></el-form-item><el-form-item label="Bug 类型"><el-select v-model="bugForm.bug_type"><el-option v-for="option in bugTypeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item><el-form-item label="当前处理人"><el-select v-model="bugForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="提出人"><el-select v-model="bugForm.reporter_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="严重程度"><el-select v-model="bugForm.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item><el-form-item label="优先级"><el-select v-model="bugForm.priority"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item></div><el-form-item label="复现步骤"><RichTextPasteEditor v-model="bugForm.reproduce_steps" /></el-form-item><el-form-item label="期望结果"><el-input v-model="bugForm.expected_result" type="textarea" :rows="2" /></el-form-item><el-form-item label="实际结果"><el-input v-model="bugForm.actual_result" type="textarea" :rows="2" /></el-form-item></el-form>
      <template #footer><el-button @click="bugDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitBug">保存</el-button></template>
    </el-dialog>

    

    <el-dialog v-model="importVisible" title="导入需求" width="720px">
      <div class="import-template-action">
        <span>请先下载固定模板，填写后上传 Excel 文件。</span>
        <el-button link type="primary" @click="downloadImportTemplate">下载模板</el-button>
      </div>
      <el-upload
        :auto-upload="false"
        :limit="1"
        accept=".xlsx"
        :on-change="onImportFileChange"
        :on-remove="clearImportFile"
      >
        <el-button>选择 Excel 文件</el-button>
      </el-upload>

      <div v-if="importPreview" class="import-preview">
        <p class="import-preview-summary">
          有效 {{ importPreview.valid_count }} 行，失败 {{ importPreview.error_count }} 行，重复 {{ importPreview.duplicate_count }} 行
        </p>
        <el-table v-if="importPreview.errors.length" :data="importPreview.errors" size="small" border>
          <el-table-column prop="row_number" label="行号" width="80" />
          <el-table-column label="错误">
            <template #default="{ row }">{{ row.messages.join('；') }}</template>
          </el-table-column>
        </el-table>
        <template v-if="importPreview.duplicates.length">
          <div class="import-strategy">
            <el-radio-group v-model="duplicateStrategy">
              <el-radio label="update_existing">更新已有需求</el-radio>
              <el-radio label="create_duplicate">重复创建</el-radio>
            </el-radio-group>
          </div>
          <el-table :data="importPreview.duplicates" size="small" border>
            <el-table-column prop="row_number" label="行号" width="80" />
            <el-table-column prop="project_name" label="项目" min-width="140" />
            <el-table-column prop="title" label="需求标题" min-width="160" />
            <el-table-column prop="existing_requirement_id" label="已有ID" width="90" />
            <el-table-column prop="existing_requirement_title" label="已有需求" min-width="160" />
          </el-table>
        </template>
      </div>

      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitImportPreview">预检</el-button>
        <el-button
          v-if="importPreview && !importPreview.error_count && importPreview.duplicate_count"
          type="success"
          :loading="saving"
          @click="submitImportCommit()"
        >
          确认导入
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createBug, deleteBug, updateBug } from '../api/bugs'
import { createIteration, deferIterationWorkItems, deleteIteration, fetchIterations, updateIteration } from '../api/iterations'
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
  saveProjectMembers,
  updateProject
} from '../api/projects'
import {
  commitRequirementImport,
  createRequirement,
  deleteRequirement,
  downloadRequirementImportTemplate,
  fetchRequirementStatusOperations,
  fetchRequirements,
  previewRequirementImport,
  updateRequirement
} from '../api/requirements'
import { createTask, deleteTask, fetchTaskStatusOperations, fetchTasks, updateTask } from '../api/tasks'
import { createBugFromTestCase, createTestCase, deleteTestCase, executeTestCase, fetchTestCaseExecutions, updateTestCase } from '../api/testCases'
import { createTestRun, deleteTestRun, updateTestRun } from '../api/testRuns'
import { fetchUsers } from '../api/users'
import { fetchAssigneeRuleConfigs } from '../api/assigneeRuleConfigs'
import { fetchWorkflowTransitionsBatch } from '../api/workflowRuntime'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import WorkflowActionButtons from '../components/WorkflowActionButtons.vue'
import { currentUserId } from '../utils/currentUser'
import { loadCloseReasonMap } from '../utils/closeReasonTooltip'
import { labelById, userLabel } from '../utils/referenceLabels'
import { formatAuditValue } from '../utils/auditHistoryLabels'
import { bugIterationOptions, includeSelectedIterationOption } from '../utils/bugIterations'
import { canCreateWorkItem, canDeleteWorkItem, canExecuteWorkItem, canManageProject, canManageTestCase, currentUserFromStorage } from '../utils/permissions'
import { deriveTaskBranch, TASK_BRANCH_OPTIONS, taskBranchLabel } from '../utils/taskBranchRules'
import { DEFAULT_BUG_TYPE_KEY } from '../utils/bugTypeOptions'
import { useBugTypes } from '../utils/useBugTypes'

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
const assigneeRuleConfigs = ref([])
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
const projectWorkflowTransitions = ref({})
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

const iterationDialogVisible = ref(false)
const deferWorkItemsVisible = ref(false)
const requirementDialogVisible = ref(false)
const taskDialogVisible = ref(false)
const caseDialogVisible = ref(false)
const caseExecutionVisible = ref(false)
const caseBugVisible = ref(false)
const runDialogVisible = ref(false)
const bugDialogVisible = ref(false)
const importVisible = ref(false)
const editingIterationId = ref(null), startingIterationId = ref(null), editingRequirementId = ref(null), editingTaskId = ref(null)
const editingCaseId = ref(null), editingRunId = ref(null), editingBugId = ref(null)
const selectedCase = ref(null)
const bugSourceCase = ref(null)
const caseExecutionHistory = ref([])
const deferWorkItemsForm = reactive({ target_iteration_id: null, remark: '' })
const settingsForm = reactive({ assignee_rule_config_id: null })

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
const requirementPriorityOptions = [
  { label: '1', value: '1' },
  { label: '2', value: '2' },
  { label: '3', value: '3' },
  { label: '4', value: '4' },
  { label: '5', value: '5' }
]
const requirementTypeOptions = ['功能', '接口', '性能', '安全', '体验', '改进', '其他']
const legacyRequirementPriorityValues = { high: '1', medium: '3', low: '5' }
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
const { bugTypeOptions } = useBugTypes()
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
  { label: '产品经理', value: 'product_owner' },
  { label: '部门负责人', value: 'department_head' },
  { label: '开发主管', value: 'tech_lead' },
  { label: '开发', value: 'developer' },
  { label: '测试主管', value: 'test_lead' },
  { label: '测试', value: 'tester' },
  { label: '观察者', value: 'viewer' }
]

const projectIterations = computed(() => projectIterationRows.value)
const projectRequirements = computed(() => projectRequirementRows.value)
const projectTasks = computed(() => projectTaskRows.value)
const projectClosed = computed(() => project.value.state_category === 'terminal')
const currentUser = computed(() => currentUserFromStorage(users.value))
const canManageCurrentProject = computed(() => canManageProject(project.value, currentUser.value, projectMembers.value))
const canCreateCurrentWorkItem = computed(() => !projectClosed.value && canCreateWorkItem(project.value, currentUser.value, projectMembers.value))
const canDeleteCurrentWorkItem = computed(() => !projectClosed.value && canDeleteWorkItem(project.value, currentUser.value, projectMembers.value))
const canManageCurrentTestCase = computed(() => canManageTestCase(project.value, currentUser.value, projectMembers.value))
const enabledWorkflowSchemes = computed(() => (
  assigneeRuleConfigs.value.filter((item) => item.lifecycle_status === 'enabled')
))
const selectedWorkflowScheme = computed(() => enabledWorkflowSchemes.value.find((item) => item.id === settingsForm.assignee_rule_config_id) || null)
const activeWorkflowScheme = computed(() => {
  const configId = project.value.assignee_rule_config_id
  if (!configId) return null
  return assigneeRuleConfigs.value.find((item) => item.id === configId) || null
})
const activeWorkflowSchemeLabel = computed(() => activeWorkflowScheme.value?.name || '未配置工作流方案')
const selectedWorkflowSchemeDescription = computed(() => selectedWorkflowScheme.value?.description || '')
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
const requirementProjectScopeIds = computed(() => collectProjectAndAncestorIds(projectId.value))
const requirementIterationDisplayOptions = computed(() => iterations.value.filter((item) => {
  const optionProjectIds = item.project_ids || []
  return optionProjectIds.some((id) => requirementProjectScopeIds.value.includes(id))
}))
const requirementIterationOptions = computed(() => requirementIterationDisplayOptions.value.filter((item) => item.state_category !== 'terminal'))
const projectRequirementOptions = computed(() => requirements.value.filter((item) => item.project_id === projectId.value))
const projectTaskOptions = computed(() => tasks.value.filter((item) => item.project_id === projectId.value))
const projectTestCaseOptions = computed(() => projectTestCaseRows.value)
const projectTestRunOptions = computed(() => projectTestRunRows.value)
const bugEditableIterationOptions = computed(() => bugIterationOptions(iterations.value, projects.value, bugForm.project_id || projectId.value))
const bugEditableIterationDisplayOptions = computed(() => includeSelectedIterationOption(bugEditableIterationOptions.value, iterations.value, bugForm.iteration_id))
const deferTargetIterations = computed(() => projectIterationOptions.value.filter((item) => item.id !== startingIterationId.value && item.state_category !== 'terminal'))
const unfinishedIterationRequirements = computed(() => requirements.value.filter((item) => item.iteration_id === startingIterationId.value && item.state_category !== 'terminal'))
const directUnfinishedIterationTasks = computed(() => tasks.value.filter((item) => item.iteration_id === startingIterationId.value && item.state_category !== 'terminal'))
const unfinishedIterationTasks = computed(() => {
  const requirementIds = new Set(unfinishedIterationRequirements.value.map((item) => item.id))
  const taskById = new Map()
  tasks.value
    .filter((item) => item.state_category !== 'terminal' && (item.iteration_id === startingIterationId.value || requirementIds.has(item.requirement_id)))
    .forEach((item) => taskById.set(item.id, item))
  return Array.from(taskById.values())
})
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
    actor: item.actor_name || '系统',
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
const iterationForm = reactive({ project_ids: [], name: '', owner_id: null, start_date: null, end_date: null, goal: '' })
const requirementForm = reactive({ project_id: null, iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: null, description: '', acceptance_criteria: '' })
const importFile = ref(null)
const importPreview = ref(null)
const duplicateStrategy = ref('')
const taskForm = reactive({ project_id: null, requirement_id: null, title: '', task_type: 'standalone_operation', priority: 'medium', owner_id: null, due_date: null, description: '' })
const caseForm = reactive({ project_id: null, requirement_id: null, title: '', case_type: 'functional', test_scope: 'functional_test', default_tester_id: null, precondition: '', steps_json: [{ step: '', expected: '' }], expected_result: '' })
const caseExecutionForm = reactive({ execute_time: '', steps_result_json: [] })
const runForm = reactive({ project_id: null, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' })
const bugForm = reactive({ project_id: null, iteration_id: null, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', bug_type: DEFAULT_BUG_TYPE_KEY, severity: '3', priority: '3', owner_id: null, reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '' })
const caseBugForm = reactive({ title: '', bug_type: DEFAULT_BUG_TYPE_KEY, severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function normalizeProjectTab(value) {
  return ['overview', 'iterations', 'requirements', 'tasks', 'tests', 'bugs', 'members', 'settings'].includes(value) ? value : 'overview'
}
function collectProjectAndAncestorIds(id) {
  const result = []
  const seen = new Set()
  let currentId = Number(id)
  while (currentId && !seen.has(currentId)) {
    seen.add(currentId)
    result.push(currentId)
    const currentProject = projects.value.find((item) => item.id === currentId)
    currentId = Number(currentProject?.parent_id || 0)
  }
  return result
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
  await loadProjectWorkflowTransitions('iteration', projectIterations.value)
}
async function loadProjectRequirementsPage() {
  if (applyProjectPage('requirements', await fetchProjectRequirements(projectId.value, projectListParams('requirements')), projectRequirementRows)) return loadProjectRequirementsPage()
  closeReasonByRequirement.value = await loadCloseReasonMap(projectRequirements.value, fetchRequirementStatusOperations)
  await loadProjectWorkflowTransitions('requirement', projectRequirements.value)
}
async function loadProjectTasksPage() {
  if (applyProjectPage('tasks', await fetchProjectTasks(projectId.value, projectListParams('tasks')), projectTaskRows)) return loadProjectTasksPage()
  closeReasonByTask.value = await loadCloseReasonMap(projectTasks.value, fetchTaskStatusOperations)
  await loadProjectWorkflowTransitions('task', projectTasks.value)
}
async function loadProjectTestCasesPage() {
  if (applyProjectPage('testCases', await fetchProjectTestCases(projectId.value, projectListParams('testCases')), projectTestCaseRows)) await loadProjectTestCasesPage()
}
async function loadProjectTestRunsPage() {
  if (applyProjectPage('testRuns', await fetchProjectTestRuns(projectId.value, projectListParams('testRuns')), projectTestRunRows)) await loadProjectTestRunsPage()
}
async function loadProjectBugsPage() {
  if (applyProjectPage('bugs', await fetchProjectBugs(projectId.value, projectListParams('bugs')), projectBugRows)) await loadProjectBugsPage()
  await loadProjectWorkflowTransitions('bug', projectBugs.value)
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
function normalizeRequirementPriority(value) { return legacyRequirementPriorityValues[value] || value || '3' }
function testRunStatusLabel(value) { return optionLabel(testRunStatusOptions, value) }
function operationActionLabel(value) { return optionLabel([{ label: '启动', value: 'start' }, { label: '挂起', value: 'suspend' }, { label: '关闭', value: 'close' }, { label: '激活', value: 'activate' }], value) }
function projectWorkflowTransitionKey(objectType, id) { return `${objectType}:${id}` }
function projectWorkflowTransitionsFor(objectType, id) { return projectWorkflowTransitions.value[projectWorkflowTransitionKey(objectType, id)] || [] }
function iterationCanDefer(row) { return projectWorkflowTransitionsFor('iteration', row.id).some((item) => ['complete', 'cancel'].includes(item.action_key)) }
async function loadProjectWorkflowTransitions(objectType, rows) {
  const items = (rows || []).map((row) => ({ object_type: objectType, id: row.id }))
  if (!items.length) return
  try {
    const { data } = await fetchWorkflowTransitionsBatch(items)
    projectWorkflowTransitions.value = {
      ...projectWorkflowTransitions.value,
      ...Object.fromEntries((data.items || []).map((item) => [projectWorkflowTransitionKey(item.object_type, item.id), item.transitions || []]))
    }
  } catch {
    projectWorkflowTransitions.value = {
      ...projectWorkflowTransitions.value,
      ...Object.fromEntries(items.map((item) => [projectWorkflowTransitionKey(item.object_type, item.id), []]))
    }
  }
}
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
function canEditWorkItem(row) { return !projectClosed.value && canExecuteWorkItem(row, currentUser.value, project.value, projectMembers.value) }
function testCaseRequirementLabel(requirementId) {
  if (!requirementId) return '-'
  return projectRequirementOptions.value.find((item) => item.id === requirementId)?.title || '-'
}
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
    assigneeRuleConfigs: assigneeRuleConfigs.value,
    iterations: projectIterationOptions.value,
    requirements: projectRequirementOptions.value,
    tasks: projectTaskOptions.value,
    testCases: projectTestCaseOptions.value,
    testRuns: projectTestRunOptions.value,
    statusOptions: [],
    priorityOptions: priorityLevelOptions,
    requirementTypeOptions,
    caseTypeOptions,
    testScopeOptions,
    executionResultOptions,
    projectMemberRoleOptions
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
    { label: '工作流配置', value: 'workflow_config_id' },
    { label: '工作流方案', value: 'assignee_rule_config_id' }
  ], field)
}
function defaultProjectMember(roles) {
  const candidates = projectMembers.value.filter((item) => roles.includes(item.project_role) && item.user_id)
  candidates.sort((left, right) => (left.sort_order ?? 0) - (right.sort_order ?? 0))
  return candidates[0]?.user_id || null
}
function activeAssigneeRuleConfig() {
  const configId = project.value.assignee_rule_config_id
  if (!configId) return null
  return assigneeRuleConfigs.value.find((item) => (
    item.id === configId && item.lifecycle_status === 'enabled'
  )) || null
}
function resetProjectSettings() {
  settingsForm.assignee_rule_config_id = project.value.assignee_rule_config_id || null
}
async function submitProjectSettings() {
  saving.value = true
  try {
    const { data } = await updateProject(projectId.value, {
      assignee_rule_config_id: settingsForm.assignee_rule_config_id || null
    })
    project.value = data
    resetProjectSettings()
    projectAuditLogs.value = (await fetchProjectAuditLogs(projectId.value)).data
    ElMessage.success('项目配置已保存')
  } finally {
    saving.value = false
  }
}
function splitAssigneeRoles(value) {
  return (value || '').split(',').map((item) => item.trim()).filter(Boolean)
}
function configuredAssigneeRoles(field, fallbackRoles) {
  const config = activeAssigneeRuleConfig()
  const roles = config ? splitAssigneeRoles(config[field]) : []
  return roles.length ? roles : []
}
function defaultTesterByRule(field, fallbackRoles) {
  return defaultProjectMember(configuredAssigneeRoles(field, fallbackRoles))
}
function addProjectMember() {
  projectMembers.value.push({
    user_id: null,
    project_role: 'developer',
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
function resetIterationForm() { Object.assign(iterationForm, { project_ids: [projectId.value], name: '', owner_id: null, start_date: null, end_date: null, goal: '' }); delete iterationForm.status }
function resetRequirementForm() { Object.assign(requirementForm, { project_id: projectId.value, iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: currentUserId(users.value), description: '', acceptance_criteria: '' }) }
function resetTaskForm() { Object.assign(taskForm, { project_id: projectId.value, requirement_id: null, title: '', task_type: 'standalone_operation', priority: 'medium', owner_id: null, due_date: null, description: '' }) }
function resetCaseForm() { Object.assign(caseForm, { project_id: projectId.value, requirement_id: null, title: '', case_type: 'functional', test_scope: 'functional_test', default_tester_id: defaultTesterByRule('test_case_tester_roles', ['tester', 'test_lead']), precondition: '', steps_json: [{ step: '', expected: '' }], expected_result: '' }) }
function resetRunForm() { Object.assign(runForm, { project_id: projectId.value, iteration_id: null, name: '', test_owner_id: defaultTesterByRule('test_run_owner_roles', ['tester', 'test_lead']), status: 'planning', remark: '' }) }
function resetBugForm() { Object.assign(bugForm, { project_id: projectId.value, iteration_id: null, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', bug_type: DEFAULT_BUG_TYPE_KEY, severity: '3', priority: '3', owner_id: null, reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '' }) }

function openIterationCreate() { editingIterationId.value = null; resetIterationForm(); iterationDialogVisible.value = true }
function openIterationEdit(row) { editingIterationId.value = row.id; Object.assign(iterationForm, { ...row, project_ids: row.project_ids || [], goal: row.goal || '' }); iterationDialogVisible.value = true }
function openDeferWorkItems(row) {
  startingIterationId.value = row.id
  Object.assign(deferWorkItemsForm, { target_iteration_id: null, remark: '' })
  deferWorkItemsVisible.value = true
}
function openRequirementCreate() { editingRequirementId.value = null; resetRequirementForm(); requirementDialogVisible.value = true }
function openRequirementEdit(row) { editingRequirementId.value = row.id; Object.assign(requirementForm, { ...row, priority: normalizeRequirementPriority(row.priority), requirement_type: row.requirement_type || '', description: row.description || '', acceptance_criteria: row.acceptance_criteria || '' }); requirementDialogVisible.value = true }
function openGenerate(row) { editingTaskId.value = null; resetTaskForm(); Object.assign(taskForm, { requirement_id: row.id, title: row.title, task_type: 'requirement_implementation', owner_id: null }); taskDialogVisible.value = true }

async function downloadImportTemplate() {
  const response = await downloadRequirementImportTemplate(projectId.value)
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = '需求导入模板.xlsx'
  link.click()
  URL.revokeObjectURL(url)
}
function openImportDialog() {
  importFile.value = null
  importPreview.value = null
  duplicateStrategy.value = ''
  importVisible.value = true
}
function onImportFileChange(file) {
  importFile.value = file.raw
  importPreview.value = null
  duplicateStrategy.value = ''
}
function clearImportFile() {
  importFile.value = null
  importPreview.value = null
  duplicateStrategy.value = ''
}
function openTaskCreate() { editingTaskId.value = null; resetTaskForm(); taskDialogVisible.value = true }
function openTaskEdit(row) {
  editingTaskId.value = row.id
  Object.assign(taskForm, {
    project_id: row.project_id || projectId.value,
    requirement_id: row.requirement_id || null,
    title: row.title || '',
    task_type: deriveTaskBranch({ requirementId: row.requirement_id, currentType: row.task_type }),
    priority: row.priority || 'medium',
    owner_id: row.owner_id || null,
    due_date: row.due_date || null,
    description: row.description || ''
  })
  taskDialogVisible.value = true
}

function taskOwnerForRequirement() { return null }
function onTaskRequirementChange(requirementId) {
  taskForm.task_type = deriveTaskBranch({ requirementId, currentType: requirementId ? null : taskForm.task_type })
  taskForm.owner_id = taskOwnerForRequirement()
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
    bug_type: DEFAULT_BUG_TYPE_KEY,
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
      assigneeRuleRes,
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
      fetchAssigneeRuleConfigs(),
      fetchIterations(),
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
    resetProjectSettings()
    projects.value = projectsRes.data
    programs.value = programRes.data; users.value = userRes.data; assigneeRuleConfigs.value = assigneeRuleRes.data
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
    await Promise.all([
      loadProjectWorkflowTransitions('iteration', projectIterations.value),
      loadProjectWorkflowTransitions('requirement', projectRequirements.value),
      loadProjectWorkflowTransitions('task', projectTasks.value),
      loadProjectWorkflowTransitions('bug', projectBugs.value)
    ])
  } catch {
    ElMessage.error('项目详情加载失败')
  } finally {
    loading.value = false
  }
}

async function refreshProjectReferences() {
  const [iterationRefRes, requirementRefRes, taskRefRes] = await Promise.all([
    fetchIterations(),
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

async function submitIteration() {
  if (!iterationForm.name.trim()) return ElMessage.warning('请填写迭代名称')
  saving.value = true
  try {
    const { status: _status, ...iterationData } = iterationForm
    const payload = { ...iterationData, project_ids: iterationForm.project_ids.length ? iterationForm.project_ids : [projectId.value], owner_id: iterationForm.owner_id || null }
    if (editingIterationId.value) await updateIteration(editingIterationId.value, payload)
    else await createIteration(payload)
    iterationDialogVisible.value = false
    await refreshAfterMutation()
  } catch (error) {
    showActionError(error, editingIterationId.value ? '迭代保存失败' : '迭代创建失败')
  } finally {
    saving.value = false
  }
}
async function submitDeferWorkItems() {
  if (!deferWorkItemsForm.target_iteration_id) return ElMessage.warning('请选择目标迭代')
  saving.value = true
  try {
    const { data } = await deferIterationWorkItems(startingIterationId.value, {
      target_iteration_id: deferWorkItemsForm.target_iteration_id,
      requirement_ids: unfinishedIterationRequirements.value.map((item) => item.id),
      task_ids: directUnfinishedIterationTasks.value.map((item) => item.id),
      remark: deferWorkItemsForm.remark
    })
    deferWorkItemsVisible.value = false
    await refreshAfterMutation()
    ElMessage.success(`已延期 ${data.moved_requirement_ids.length} 个需求、${data.moved_task_ids.length} 个任务`)
  } catch (error) {
    showActionError(error, '延期未完成项失败')
  } finally {
    saving.value = false
  }
}
async function submitRequirement() {
  if (!requirementForm.title.trim()) return ElMessage.warning('请填写需求标题')
  saving.value = true
  try {
    const { status: _status, ...formData } = requirementForm
    const payload = { ...formData, project_id: projectId.value, iteration_id: requirementForm.iteration_id || null, owner_id: requirementForm.owner_id || null, proposer_id: requirementForm.proposer_id || null }
    if (editingRequirementId.value) await updateRequirement(editingRequirementId.value, payload)
    else await createRequirement(payload)
    requirementDialogVisible.value = false
    await refreshAfterMutation()
  } catch (error) {
    showActionError(error, editingRequirementId.value ? '需求保存失败' : '需求创建失败')
  } finally {
    saving.value = false
  }
}
async function submitImportPreview() {
  if (!importFile.value) return ElMessage.warning('请选择 Excel 文件')
  saving.value = true
  try {
    const { data } = await previewRequirementImport(importFile.value, projectId.value)
    importPreview.value = data
    if (data.error_count) return
    if (!data.duplicate_count) await submitImportCommit('create_duplicate')
  } catch (error) {
    showActionError(error, '导入预检失败')
  } finally {
    saving.value = false
  }
}
async function submitImportCommit(strategy = duplicateStrategy.value) {
  if (!importFile.value) return ElMessage.warning('请选择 Excel 文件')
  if (importPreview.value?.duplicate_count && !strategy) return ElMessage.warning('请选择重复处理方式')
  saving.value = true
  try {
    const { data } = await commitRequirementImport(importFile.value, strategy || 'create_duplicate', projectId.value)
    importVisible.value = false
    await refreshAfterMutation()
    ElMessage.success(`导入完成，新增 ${data.created_count} 条，更新 ${data.updated_count} 条`)
  } catch (error) {
    showActionError(error, '导入需求失败')
  } finally {
    saving.value = false
  }
}
async function submitTask() {
  if (!taskForm.title.trim()) return ElMessage.warning('请填写任务标题')
  saving.value = true
  try {
    const payload = { ...taskForm, project_id: projectId.value, requirement_id: taskForm.requirement_id || null, task_type: deriveTaskBranch({ requirementId: taskForm.requirement_id, currentType: taskForm.task_type }), owner_id: taskForm.owner_id || null }
    if (editingTaskId.value) await updateTask(editingTaskId.value, payload)
    else await createTask(payload)
    taskDialogVisible.value = false
    await refreshAfterMutation()
  } catch (error) {
    showActionError(error, editingTaskId.value ? '任务保存失败' : '任务创建失败')
  } finally {
    saving.value = false
  }
}
async function submitCase() {
  if (!caseForm.title.trim()) return ElMessage.warning('请填写用例标题')
  saving.value = true
  try {
    const payload = { ...caseForm, project_id: projectId.value, requirement_id: caseForm.requirement_id || null, default_tester_id: caseForm.default_tester_id || null, steps_json: cleanCaseSteps() }
    if (editingCaseId.value) await updateTestCase(editingCaseId.value, payload)
    else await createTestCase(payload)
    caseDialogVisible.value = false
    await refreshAfterMutation()
  } catch (error) {
    showActionError(error, editingCaseId.value ? '用例保存失败' : '用例创建失败')
  } finally {
    saving.value = false
  }
}
async function submitCaseExecution() {
  saving.value = true
  try {
    const currentId = selectedCase.value.id
    await executeTestCase(currentId, { execute_time: caseExecutionForm.execute_time, steps_result_json: caseExecutionForm.steps_result_json })
    await refreshAfterMutation()
    ElMessage.success('用例执行结果已保存')
    await openNextCaseAfterExecution(currentId, projectTestCases.value)
  } catch (error) {
    showActionError(error, '用例执行结果保存失败')
  } finally {
    saving.value = false
  }
}
async function submitRun() {
  if (!runForm.name.trim()) return ElMessage.warning('请填写测试单名称')
  saving.value = true
  try {
    const payload = { ...runForm, project_id: projectId.value, iteration_id: runForm.iteration_id || null, test_owner_id: runForm.test_owner_id || null }
    if (editingRunId.value) await updateTestRun(editingRunId.value, payload)
    else await createTestRun(payload)
    runDialogVisible.value = false
    await refreshAfterMutation()
  } catch (error) {
    showActionError(error, editingRunId.value ? '测试单保存失败' : '测试单创建失败')
  } finally {
    saving.value = false
  }
}
async function submitBug() {
  if (!bugForm.title.trim()) return ElMessage.warning('请填写 Bug 标题')
  saving.value = true
  try {
    const payload = { ...bugForm, project_id: projectId.value, iteration_id: bugForm.iteration_id || null, requirement_id: bugForm.requirement_id || null, task_id: bugForm.task_id || null, test_case_id: bugForm.test_case_id || null, test_run_id: bugForm.test_run_id || null, owner_id: bugForm.owner_id || null, reporter_id: bugForm.reporter_id || null }
    if (editingBugId.value) await updateBug(editingBugId.value, payload)
    else await createBug(payload)
    bugDialogVisible.value = false
    await refreshAfterMutation()
  } catch (error) {
    showActionError(error, editingBugId.value ? 'Bug 保存失败' : 'Bug 创建失败')
  } finally {
    saving.value = false
  }
}
async function submitCaseBug() {
  if (!caseBugForm.title.trim()) return ElMessage.warning('请填写 Bug 标题')
  saving.value = true
  try {
    await createBugFromTestCase(bugSourceCase.value.id, { ...caseBugForm })
    caseBugVisible.value = false
    await refreshAfterMutation()
    ElMessage.success('Bug 已提交')
  } catch (error) {
    showActionError(error, 'Bug 提交失败')
  } finally {
    saving.value = false
  }
}
async function removeIteration(id) { try { await deleteIteration(id); await refreshAfterMutation() } catch (error) { showActionError(error, '迭代删除失败') } }
async function removeRequirement(id) { try { await deleteRequirement(id); await refreshAfterMutation() } catch (error) { showActionError(error, '需求删除失败') } }
async function removeTask(id) { try { await deleteTask(id); await refreshAfterMutation() } catch (error) { showActionError(error, '任务删除失败') } }
async function removeCase(id) { try { await deleteTestCase(id); await refreshAfterMutation() } catch (error) { showActionError(error, '用例删除失败') } }
async function removeRun(id) { try { await deleteTestRun(id); await refreshAfterMutation() } catch (error) { showActionError(error, '测试单删除失败') } }
async function removeBug(id) { try { await deleteBug(id); await refreshAfterMutation() } catch (error) { showActionError(error, 'Bug 删除失败') } }

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

<style scoped>
.defer-work-form {
  margin-top: 16px;
}

.defer-work-lists {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}

.defer-work-lists h3 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}
</style>
