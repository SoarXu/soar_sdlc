<template>
  <section class="project-detail-page">
    <div class="project-detail-head">
      <div>
        <el-button link type="primary" @click="$router.push('/iterations')">返回迭代列表</el-button>
        <h1>{{ iteration.name || '迭代详情' }}</h1>
        <p>{{ projectNames }} · {{ userLabel(users, iteration.owner_id) }} · {{ iteration.start_date || '-' }} 至 {{ iteration.end_date || '-' }}</p>
      </div>
      <div class="iteration-head-actions">
        <WorkflowActionButtons
          v-if="canManageIteration && iteration.id"
          object-type="iteration"
          :object-id="iteration.id"
          :transitions="iterationWorkflowTransitionsFor('iteration', iteration.id)"
          :auto-load="false"
          :users="users"
          @executed="loadData"
        />
        <el-tag size="large">{{ iteration.status_name || '-' }}</el-tag>
      </div>
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
        <div class="metrics project-detail-metrics">
          <el-card shadow="never"><span>需求数</span><strong>{{ metrics.requirement_total || 0 }}</strong></el-card>
          <el-card shadow="never"><span>任务数</span><strong>{{ tasks.length }}</strong></el-card>
          <el-card shadow="never"><span>用例数</span><strong>{{ testCases.length }}</strong></el-card>
          <el-card shadow="never"><span>Bug 数</span><strong>{{ bugs.length }}</strong></el-card>
          <el-card shadow="never"><span>迭代进度</span><strong>{{ percent(metrics.progress_rate) }}</strong></el-card>
          <el-card shadow="never"><span>测试覆盖率</span><strong>{{ percent(metrics.test_coverage_rate) }}</strong></el-card>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="迭代名称">{{ iteration.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ userLabel(users, iteration.owner_id) }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ iteration.start_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ iteration.end_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际开始">{{ iteration.actual_start_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际结束">{{ iteration.actual_end_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标" :span="2">{{ iteration.goal || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <template v-else-if="activeTab === 'requirements'">
        <div class="project-tab-toolbar"><el-button v-if="canManageIteration" type="primary" @click="openRequirementLink">关联需求</el-button></div>
        <div v-if="!requirements.length" class="project-tab-placeholder">暂无关联需求</div>
        <div v-else class="iteration-tree-list">
          <div v-for="project in flatProjects" :key="project.id" class="iteration-project-block">
            <h3 v-if="requirementsByProject(project.id).length">{{ project.name }}</h3>
            <el-table v-if="requirementsByProject(project.id).length" :data="requirementsByProject(project.id)" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column label="需求标题" min-width="180" show-overflow-tooltip>
                <template #default="{ row }"><router-link class="table-link" :to="requirementDetailLink(row)">{{ row.title }}</router-link></template>
              </el-table-column>
              <el-table-column label="迭代" width="140"><template #default>{{ iteration.name || '-' }}</template></el-table-column>
              <el-table-column label="负责人" width="130"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
              <el-table-column label="优先级" width="100"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tooltip v-if="closeReasonByRequirement[row.id]" :content="closeReasonByRequirement[row.id]" placement="top" raw-content>
                    <span class="status-with-reason">{{ row.status_name || '-' }}</span>
                  </el-tooltip>
                  <span v-else>{{ row.status_name || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" :width="requirementOperationWidth" fixed="right">
                <template #default="{ row }">
                  <div class="table-actions">
                    <el-button v-if="canEditWorkItem(row)" link type="primary" @click="openRequirementEdit(row)">编辑</el-button>
                    <WorkflowActionButtons
                      object-type="requirement"
                      :object-id="row.id"
                      mode="list"
                      :transitions="iterationWorkflowTransitionsFor('requirement', row.id)"
                      :auto-load="false"
                      :users="users"
                      @executed="loadData"
                    />
                    <el-button v-if="canEditWorkItem(row)" link type="success" @click="openGenerateTask(row)">生成任务</el-button>
                    <el-button v-if="canManageTestCaseFor(row.project_id)" link type="success" @click="goProjectTab(row.project_id, 'tests')">建用例</el-button>
                    <el-popconfirm v-if="canDeleteWorkItemFor(row.project_id)" title="确认删除该需求？" @confirm="deleteRequirementRow(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
                    <el-button v-if="canManageIteration" link type="danger" @click="removeRequirement(row.id)">移除</el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'tasks'">
        <div class="project-tab-toolbar"><el-button v-if="canManageIteration" type="primary" @click="openTaskLink">关联任务</el-button></div>
        <div v-for="project in flatProjects" :key="project.id" class="iteration-project-block">
          <h3 v-if="tasksByProject(project.id).length">{{ project.name }}</h3>
          <el-table v-if="tasksByProject(project.id).length" :data="tasksByProject(project.id)" stripe width="100%">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column label="任务标题" min-width="180" show-overflow-tooltip><template #default="{ row }"><router-link class="table-link" :to="taskDetailLink(row)">{{ row.title }}</router-link></template></el-table-column>
            <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
            <el-table-column label="任务分支" width="120"><template #default="{ row }">{{ taskBranchLabel(row.task_type) }}</template></el-table-column>
            <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
            <el-table-column prop="due_date" label="截止日期" width="130" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tooltip v-if="closeReasonByTask[row.id]" :content="closeReasonByTask[row.id]" placement="top" raw-content>
                  <span class="status-with-reason">{{ row.status_name || '-' }}</span>
                </el-tooltip>
                <span v-else>{{ row.status_name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" :width="taskOperationWidth" fixed="right">
              <template #default="{ row }">
                <div class="table-actions">
                  <el-button v-if="canEditWorkItem(row)" link type="primary" @click="openTaskEdit(row)">编辑</el-button>
                  <WorkflowActionButtons object-type="task" :object-id="row.id" mode="list" :transitions="iterationWorkflowTransitionsFor('task', row.id)" :auto-load="false" :users="users" @executed="loadData" /><el-popconfirm v-if="canDeleteWorkItemFor(row.project_id)" title="确认删除该任务？" @confirm="deleteTaskRow(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
                  <el-button v-if="canManageIteration && row.iteration_id === iterationId" link type="danger" @click="removeTask(row.id)">移除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>

      <template v-else-if="activeTab === 'cases'">
        <div v-if="!testCases.length" class="project-tab-placeholder">暂无关联用例</div>
        <div v-else class="iteration-tree-list">
          <div v-for="project in flatProjects" :key="project.id" class="iteration-project-block">
            <h3 v-if="testCasesByProject(project.id).length">{{ project.name }}</h3>
            <el-table v-if="testCasesByProject(project.id).length" :data="testCasesByProject(project.id)" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column label="用例标题" min-width="180" show-overflow-tooltip>
                <template #default="{ row }"><router-link class="table-link" :to="{ name: 'test-case-detail', params: { id: row.id }, query: { from: 'iteration', iterationId: iterationId, tab: 'cases' } }">{{ row.title }}</router-link></template>
              </el-table-column>
              <el-table-column label="需求" min-width="180"><template #default="{ row }">{{ testCaseRequirementLabel(row.requirement_id) }}</template></el-table-column>
              <el-table-column label="测试人" width="140"><template #default="{ row }">{{ userLabel(users, row.default_tester_id) }}</template></el-table-column>
              <el-table-column label="类型" width="120"><template #default="{ row }">{{ caseTypeLabel(row.case_type) }}</template></el-table-column>
              <el-table-column label="适用范围" width="150"><template #default="{ row }">{{ testScopeLabel(row.test_scope) }}</template></el-table-column>
              <el-table-column label="最近执行时间" width="170"><template #default="{ row }">{{ formatDateTime(row.last_execute_time) }}</template></el-table-column>
              <el-table-column label="最近结果" width="110"><template #default="{ row }">{{ executionResultLabel(row.last_execute_result) }}</template></el-table-column>
              <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button v-if="canManageTestCaseFor(row.project_id)" link type="success" @click="openCaseExecution(row)">执行</el-button><el-button v-if="canManageTestCaseFor(row.project_id)" link type="warning" :disabled="!canCreateBugFromCase(row)" @click="openCaseBug(row)">提 Bug</el-button></template></el-table-column>
            </el-table>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'bugs'">
        <el-table :data="bugs" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="Bug 标题" min-width="180" show-overflow-tooltip>
            <template #default="{ row }"><router-link class="table-link" :to="{ name: 'bug-detail', params: { id: row.id }, query: { from: 'iteration', iterationId: iterationId, tab: 'bugs' } }">{{ row.title }}</router-link></template>
          </el-table-column>
          <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
          <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column label="Bug 类型" width="120"><template #default="{ row }">{{ row.bug_type || '-' }}</template></el-table-column>
          <el-table-column label="严重程度" width="110"><template #default="{ row }"><RequirementPriorityBadge :value="row.severity" /></template></el-table-column>
          <el-table-column label="优先级" width="110"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
          <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column label="状态" width="110"><template #default="{ row }">{{ row.status_name || '-' }}</template></el-table-column>
        </el-table>
      </template>
    </el-card>

    <el-dialog v-model="requirementDialogVisible" title="关联需求" width="760px">
      <el-table :data="availableRequirements" @selection-change="selectedRequirementIds = $event.map(item => item.id)" max-height="420">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="title" label="需求标题" min-width="240" />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }">{{ row.status_name || '-' }}</template></el-table-column>
      </el-table>
      <template #footer><el-button @click="requirementDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirements">关联</el-button></template>
    </el-dialog>

    <el-dialog v-model="taskDialogVisible" title="关联任务" width="760px">
      <el-table :data="availableTasks" @selection-change="selectedTaskIds = $event.map(item => item.id)" max-height="420">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="title" label="任务标题" min-width="240" />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }">{{ row.status_name || '-' }}</template></el-table-column>
      </el-table>
      <template #footer><el-button @click="taskDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTasks">关联</el-button></template>
    </el-dialog>

    <el-dialog v-model="generateTaskVisible" title="从需求生成任务" width="620px">
      <el-form label-position="top">
        <el-form-item label="需求">
          <el-input :model-value="generatingRequirement?.title || '-'" disabled />
        </el-form-item>
        <el-form-item label="任务标题" required>
          <el-input v-model="generateTaskForm.title" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="任务分支">
            <el-select v-model="generateTaskForm.task_type" disabled>
              <el-option v-for="option in TASK_BRANCH_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="generateTaskForm.priority">
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item label="截止日期">
            <el-date-picker v-model="generateTaskForm.due_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
        </div>
        <el-form-item label="描述">
          <el-input v-model="generateTaskForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateTaskVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitGenerateTask">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="requirementEditVisible" title="编辑需求" width="640px">
      <el-form label-position="top">
        <el-form-item label="需求标题" required><el-input v-model="requirementForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="提出人">
            <el-select v-model="requirementForm.proposer_id" clearable filterable>
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="requirementForm.requirement_type">
              <el-option v-for="option in requirementTypeOptions" :key="option" :label="option" :value="option" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="requirementForm.priority" class="priority-select">
              <template #prefix><RequirementPriorityBadge :value="requirementForm.priority" /></template>
              <el-option v-for="option in requirementPriorityOptions" :key="option.value" :label="option.label" :value="option.value">
                <RequirementPriorityBadge :value="option.value" />
              </el-option>
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="需求描述"><el-input v-model="requirementForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="requirementForm.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="requirementEditVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirementEdit">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="deferWorkItemsVisible" title="处理未完成项" width="720px">
      <el-alert title="当前迭代存在未完成需求或任务，请先延期到其他迭代后再结束当前迭代。" type="warning" :closable="false" show-icon />
      <el-form label-position="top" class="defer-work-form">
        <el-form-item label="目标迭代" required>
          <el-select v-model="deferWorkItemsForm.target_iteration_id" filterable placeholder="请选择目标迭代">
            <el-option v-for="item in deferTargetIterations" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="deferWorkItemsForm.remark" type="textarea" :rows="2" placeholder="例如：延期到下一迭代继续处理" /></el-form-item>
      </el-form>
      <div class="defer-work-lists">
        <div>
          <h3>未完成需求 {{ unfinishedIterationRequirements.length }}</h3>
          <el-table :data="unfinishedIterationRequirements" max-height="220" border>
            <el-table-column prop="title" label="标题" min-width="220" />
            <el-table-column label="状态" width="100"><template #default="{ row }">{{ row.status_name || '-' }}</template></el-table-column>
            <el-table-column label="负责人" width="120"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          </el-table>
        </div>
        <div>
          <h3>未完成任务 {{ unfinishedIterationTasks.length }}</h3>
          <el-table :data="unfinishedIterationTasks" max-height="220" border>
            <el-table-column prop="title" label="标题" min-width="220" />
            <el-table-column label="状态" width="100"><template #default="{ row }">{{ row.status_name || '-' }}</template></el-table-column>
            <el-table-column label="负责人" width="120"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <el-button @click="deferWorkItemsVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitDeferWorkItems">延期到目标迭代</el-button>
      </template>
    </el-dialog>

    

    <el-dialog v-model="taskEditVisible" title="编辑任务" width="620px">
      <el-form label-position="top">
        <el-form-item label="任务标题" required><el-input v-model="taskEditForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="需求">
            <el-select v-model="taskEditForm.requirement_id" clearable filterable @change="onTaskRequirementChange">
              <el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="任务分支"><el-select v-model="taskEditForm.task_type" :disabled="Boolean(taskEditForm.requirement_id)"><el-option v-for="option in TASK_BRANCH_OPTIONS" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="taskEditForm.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item>
          <el-form-item label="截止日期"><el-date-picker v-model="taskEditForm.due_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
        </div>
        <el-form-item label="描述"><el-input v-model="taskEditForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="taskEditVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTaskEdit">保存</el-button></template>
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
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deferIterationWorkItems,
  fetchAvailableIterationRequirements,
  fetchAvailableIterationTasks,
  fetchIterationDetail,
  fetchIterations,
  linkIterationRequirements,
  linkIterationTasks,
  unlinkIterationRequirement,
  unlinkIterationTask
} from '../api/iterations'
import { createBugFromTestCase, executeTestCase, fetchTestCaseExecutions } from '../api/testCases'
import { deleteRequirement, fetchRequirementStatusOperations, updateRequirement } from '../api/requirements'
import { createLinkedTask, deleteTask, fetchTaskStatusOperations, updateTask } from '../api/tasks'
import { fetchProjectMembers } from '../api/projects'
import { fetchUsers } from '../api/users'
import { fetchWorkflowTransitionsBatch } from '../api/workflowRuntime'
import { workflowActionColumnWidth } from '../utils/workflowActionColumn'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import WorkflowActionButtons from '../components/WorkflowActionButtons.vue'
import { loadCloseReasonMap } from '../utils/closeReasonTooltip'
import { labelById, userLabel } from '../utils/referenceLabels'
import { canCreateWorkItem, canDeleteWorkItem, canExecuteWorkItem, canManageProject, canManageTestCase, currentUserFromStorage } from '../utils/permissions'
import { deriveTaskBranch, TASK_BRANCH_OPTIONS, taskBranchLabel } from '../utils/taskBranchRules'
import { DEFAULT_BUG_TYPE_KEY } from '../utils/bugTypeOptions'
import { useBugTypes } from '../utils/useBugTypes'

const route = useRoute()
const router = useRouter()
const iterationId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const activeTab = ref(normalizeIterationTab(route.query.tab))
const iteration = ref({})
const projects = ref([])
const iterations = ref([])
const requirements = ref([])
const tasks = ref([])
const testCases = ref([])
const bugs = ref([])
const iterationWorkflowTransitions = ref({})
const requirementOperationWidth = computed(() => workflowActionColumnWidth(
  requirements.value.map((row) => iterationWorkflowTransitionsFor('requirement', row.id)),
  { minWidth: 260, extraWidth: 220 }
))
const taskOperationWidth = computed(() => workflowActionColumnWidth(
  tasks.value.map((row) => iterationWorkflowTransitionsFor('task', row.id)),
  { minWidth: 220, extraWidth: 130 }
))
const metrics = ref({})
const users = ref([])
const projectMembersById = ref({})
const availableRequirements = ref([])
const availableTasks = ref([])
const selectedRequirementIds = ref([])
const selectedTaskIds = ref([])
const requirementDialogVisible = ref(false)
const requirementEditVisible = ref(false)
const taskDialogVisible = ref(false)
const taskEditVisible = ref(false)
const generateTaskVisible = ref(false)
const deferWorkItemsVisible = ref(false)
const editingTaskId = ref(null)
const caseExecutionVisible = ref(false)
const caseBugVisible = ref(false)
const selectedCase = ref(null)
const bugSourceCase = ref(null)
const caseExecutionHistory = ref([])
const caseExecutionForm = ref({ execute_time: '', steps_result_json: [] })
const deferWorkItemsForm = ref({ target_iteration_id: null, remark: '' })
const closeReasonByRequirement = ref({})
const closeReasonByTask = ref({})
const generatingRequirement = ref(null)
const tabs = [
  { key: 'overview', label: '概览' },
  { key: 'requirements', label: '需求' },
  { key: 'tasks', label: '任务' },
  { key: 'cases', label: '用例' },
  { key: 'bugs', label: 'Bug' }
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
const { bugTypeOptions } = useBugTypes()
const requirementTypeOptions = ['功能', '接口', '性能', '安全', '体验', '改进', '其他']
const requirementPriorityOptions = [
  { label: '① 最高', value: '1' },
  { label: '② 高', value: '2' },
  { label: '③ 中', value: '3' },
  { label: '④ 低', value: '4' },
  { label: '⑤ 最低', value: '5' }
]
const priorityLevelOptions = [
  { label: '① 最高', value: '1' },
  { label: '② 高', value: '2' },
  { label: '③ 中', value: '3' },
  { label: '④ 低', value: '4' },
  { label: '⑤ 最低', value: '5' }
]
const caseBugForm = ref({ title: '', bug_type: DEFAULT_BUG_TYPE_KEY, severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })
const editingRequirementId = ref(null)
const requirementForm = reactive({ project_id: null, iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: null, description: '', acceptance_criteria: '' })
const taskEditForm = reactive({ project_id: null, requirement_id: null, title: '', task_type: 'standalone_operation', priority: 'medium', owner_id: null, due_date: null, description: '' })
const generateTaskForm = reactive({ title: '', task_type: 'requirement_implementation', priority: 'medium', due_date: null, description: '' })
const flatProjects = computed(() => flattenProjects(projects.value))
const currentUser = computed(() => currentUserFromStorage(users.value))
const canManageIteration = computed(() => (iteration.value.project_ids || []).some((projectId) => canManageProjectFor(projectId)))
const projectNames = computed(() => (iteration.value.project_ids || []).map(id => labelById(flatProjects.value, id)).join('、') || '-')
const failedExecutionCount = computed(() => caseExecutionHistory.value.filter((item) => item.result === 'failed').length)
const deferTargetIterations = computed(() => iterations.value.filter((item) => item.id !== iterationId.value && item.state_category !== 'terminal'))
const unfinishedIterationRequirements = computed(() => requirements.value.filter((item) => item.state_category !== 'terminal'))
const directUnfinishedIterationTasks = computed(() => tasks.value.filter((item) => item.iteration_id === iterationId.value && item.state_category !== 'terminal'))
const unfinishedIterationTasks = computed(() => tasks.value.filter((item) => item.state_category !== 'terminal'))

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function caseTypeLabel(value) { return optionLabel(caseTypeOptions, value) }
function testScopeLabel(value) { return optionLabel(testScopeOptions, value) }
function executionResultLabel(value) { return optionLabel(executionResultOptions, value) }
function canCreateBugFromCase(row) { return ['failed', 'blocked'].includes(row.last_execute_result) }
function testCaseRequirementLabel(requirementId) {
  if (!requirementId) return '-'
  return requirements.value.find((item) => item.id === requirementId)?.title || '-'
}
function requirementsByProject(projectId) { return requirements.value.filter((item) => item.project_id === projectId) }
function tasksByProject(projectId) { return tasks.value.filter((item) => item.project_id === projectId) }
function testCasesByProject(projectId) { return testCases.value.filter((item) => item.project_id === projectId) }
function requirementDetailLink(row) { return { name: 'requirement-detail', params: { id: row.id }, query: { from: 'iteration', iterationId: iterationId.value, tab: 'requirements' } } }
function taskDetailLink(row) { return { name: 'task-detail', params: { id: row.id }, query: { from: 'iteration', iterationId: iterationId.value, tab: 'tasks' } } }
function projectById(projectId) { return flatProjects.value.find((item) => item.id === projectId) || null }
function membersForProject(projectId) { return projectMembersById.value[projectId] || [] }
function canManageProjectFor(projectId) { return canManageProject(projectById(projectId), currentUser.value, membersForProject(projectId)) }
function canCreateWorkItemFor(projectId) { return canCreateWorkItem(projectById(projectId), currentUser.value, membersForProject(projectId)) }
function canDeleteWorkItemFor(projectId) { return canDeleteWorkItem(projectById(projectId), currentUser.value, membersForProject(projectId)) }
function canManageTestCaseFor(projectId) { return canManageTestCase(projectById(projectId), currentUser.value, membersForProject(projectId)) }
function canEditWorkItem(row) { return canExecuteWorkItem(row, currentUser.value, projectById(row.project_id), membersForProject(row.project_id)) }
function percent(value) { return `${Math.round((value || 0) * 100)}%` }
function flattenProjects(items) { return items.flatMap((item) => [item, ...flattenProjects(item.children || [])]) }
function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function executionHistoryTitle(item) { return `#${item.id} ${formatDateTime(item.execute_time)}，结果为 ${executionResultLabel(item.result)}` }
function defaultExecutionTime() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
function normalizeCaseSteps(value) { return Array.isArray(value) && value.length ? value.map((item) => ({ step: item.step || '', expected: item.expected || '' })) : [{ step: '', expected: '' }] }
function normalizeRequirementPriority(value) { return ['1', '2', '3', '4', '5'].includes(String(value || '')) ? String(value) : '3' }
function normalizeIterationTab(value) { return ['overview', 'requirements', 'tasks', 'cases', 'bugs'].includes(value) ? value : 'overview' }
function setActiveTab(key) {
  activeTab.value = key
  router.replace({ name: 'iteration-detail', params: { id: iterationId.value }, query: { ...route.query, tab: key } })
}
function apiErrorMessage(error, fallback) { return error?.response?.data?.detail || fallback }
function showActionError(error, fallback) { ElMessageBox.alert(apiErrorMessage(error, fallback), '提示', { type: 'warning' }) }
function goProjectTab(projectId, tab) { router.push({ name: 'project-detail', params: { id: projectId }, query: { tab } }) }
function iterationWorkflowTransitionKey(objectType, id) { return `${objectType}:${id}` }
function iterationWorkflowTransitionsFor(objectType, id) { return iterationWorkflowTransitions.value[iterationWorkflowTransitionKey(objectType, id)] || [] }

async function loadData() {
  loading.value = true
  try {
    const [detailRes, userRes] = await Promise.all([fetchIterationDetail(iterationId.value), fetchUsers()])
    iteration.value = detailRes.data.iteration
    projects.value = detailRes.data.projects
    requirements.value = detailRes.data.requirements
    tasks.value = detailRes.data.tasks
    testCases.value = detailRes.data.test_cases
    bugs.value = detailRes.data.bugs || []
    metrics.value = detailRes.data.metrics
    users.value = userRes.data
    await loadProjectMembers()
    const projectId = iteration.value.project_ids?.[0]
    iterations.value = projectId ? (await fetchIterations({ project_id: projectId })).data : []
    closeReasonByRequirement.value = await loadCloseReasonMap(requirements.value, fetchRequirementStatusOperations)
    closeReasonByTask.value = await loadCloseReasonMap(tasks.value, fetchTaskStatusOperations)
    await loadIterationWorkflowTransitions()
  } catch {
    ElMessage.error('迭代详情加载失败')
  } finally {
    loading.value = false
  }
}

async function loadProjectMembers() {
  const entries = await Promise.all(flatProjects.value.map(async (project) => {
    try {
      const { data } = await fetchProjectMembers(project.id)
      return [project.id, data]
    } catch {
      return [project.id, []]
    }
  }))
  projectMembersById.value = Object.fromEntries(entries)
}

async function loadIterationWorkflowTransitions() {
  const items = [
    { object_type: 'iteration', id: iterationId.value },
    ...requirements.value.map((item) => ({ object_type: 'requirement', id: item.id })),
    ...tasks.value.map((item) => ({ object_type: 'task', id: item.id })),
    ...bugs.value.map((item) => ({ object_type: 'bug', id: item.id }))
  ]
  if (!items.length) {
    iterationWorkflowTransitions.value = {}
    return
  }
  const { data } = await fetchWorkflowTransitionsBatch(items)
  iterationWorkflowTransitions.value = Object.fromEntries((data.items || []).map((item) => [iterationWorkflowTransitionKey(item.object_type, item.id), item.transitions || []]))
}

async function openRequirementLink() {
  selectedRequirementIds.value = []
  availableRequirements.value = (await fetchAvailableIterationRequirements(iterationId.value)).data
  requirementDialogVisible.value = true
}
async function submitRequirements() {
  if (!selectedRequirementIds.value.length) return ElMessage.warning('请选择需求')
  saving.value = true
  try {
    await linkIterationRequirements(iterationId.value, selectedRequirementIds.value)
    requirementDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}
async function removeRequirement(requirementId) { await unlinkIterationRequirement(iterationId.value, requirementId); await loadData() }
function openRequirementEdit(row) {
  editingRequirementId.value = row.id
  Object.assign(requirementForm, {
    ...row,
    priority: normalizeRequirementPriority(row.priority),
    requirement_type: row.requirement_type || '功能',
    owner_id: row.owner_id || null,
    proposer_id: row.proposer_id || null,
    description: row.description || '',
    acceptance_criteria: row.acceptance_criteria || '',
  })
  requirementEditVisible.value = true
}
async function submitRequirementEdit() {
  if (!requirementForm.title.trim()) return ElMessage.warning('请填写需求标题')
  saving.value = true
  try {
    const { status: _status, ...formData } = requirementForm
    await updateRequirement(editingRequirementId.value, {
      ...formData,
      project_id: requirementForm.project_id,
      iteration_id: requirementForm.iteration_id || null,
      owner_id: requirementForm.owner_id || null,
      proposer_id: requirementForm.proposer_id || null
    })
    requirementEditVisible.value = false
    await loadData()
    ElMessage.success('需求已保存')
  } finally {
    saving.value = false
  }
}
async function deleteRequirementRow(id) { await deleteRequirement(id); await loadData() }

function openGenerateTask(row) {
  generatingRequirement.value = row
  Object.assign(generateTaskForm, {
    title: row.title || '',
    task_type: 'requirement_implementation',
    priority: row.priority || 'medium',
    due_date: null,
    description: ''
  })
  generateTaskVisible.value = true
}
async function submitGenerateTask() {
  if (!generateTaskForm.title.trim()) return ElMessage.warning('请填写任务标题')
  saving.value = true
  try {
    const payload = {
      source_type: 'requirement',
      source_id: generatingRequirement.value.id,
      ...generateTaskForm,
      due_date: generateTaskForm.due_date || null
    }
    await createLinkedTask(payload)
    generateTaskVisible.value = false
    await loadData()
    setActiveTab('tasks')
    ElMessage.success('任务已生成')
  } finally {
    saving.value = false
  }
}

async function openTaskLink() {
  selectedTaskIds.value = []
  availableTasks.value = (await fetchAvailableIterationTasks(iterationId.value)).data
  taskDialogVisible.value = true
}
async function submitTasks() {
  if (!selectedTaskIds.value.length) return ElMessage.warning('请选择任务')
  saving.value = true
  try {
    await linkIterationTasks(iterationId.value, selectedTaskIds.value)
    taskDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}
async function removeTask(taskId) { await unlinkIterationTask(iterationId.value, taskId); await loadData() }
function openTaskEdit(row) {
  editingTaskId.value = row.id
  Object.assign(taskEditForm, {
    project_id: row.project_id || null,
    requirement_id: row.requirement_id || null,
    title: row.title || '',
    task_type: deriveTaskBranch({ requirementId: row.requirement_id, currentType: row.task_type }),
    priority: row.priority || 'medium',
    owner_id: row.owner_id || null,
    due_date: row.due_date || null,
    description: row.description || ''
  })
  taskEditVisible.value = true
}
function onTaskRequirementChange(requirementId) {
  taskEditForm.task_type = deriveTaskBranch({ requirementId, currentType: requirementId ? null : taskEditForm.task_type })
}
async function submitTaskEdit() {
  if (!taskEditForm.title.trim()) return ElMessage.warning('请填写任务标题')
  saving.value = true
  try {
    await updateTask(editingTaskId.value, {
      ...taskEditForm,
      requirement_id: taskEditForm.requirement_id || null,
      task_type: deriveTaskBranch({ requirementId: taskEditForm.requirement_id, currentType: taskEditForm.task_type }),
      owner_id: taskEditForm.owner_id || null
    })
    taskEditVisible.value = false
    await loadData()
    ElMessage.success('任务已保存')
  } catch (error) {
    showActionError(error, '任务保存失败')
  } finally {
    saving.value = false
  }
}
async function submitDeferWorkItems() {
  if (!deferWorkItemsForm.value.target_iteration_id) return ElMessage.warning('请选择目标迭代')
  saving.value = true
  try {
    const { data } = await deferIterationWorkItems(iterationId.value, {
      target_iteration_id: deferWorkItemsForm.value.target_iteration_id,
      requirement_ids: unfinishedIterationRequirements.value.map((item) => item.id),
      task_ids: directUnfinishedIterationTasks.value.map((item) => item.id),
      remark: deferWorkItemsForm.value.remark
    })
    deferWorkItemsVisible.value = false
    await loadData()
    ElMessage.success(`已延期 ${data.moved_requirement_ids.length} 个需求、${data.moved_task_ids.length} 个任务`)
  } catch (error) {
    showActionError(error, '延期未完成项失败')
  } finally {
    saving.value = false
  }
}
async function deleteTaskRow(id) { await deleteTask(id); await loadData() }
async function openCaseExecution(row) {
  selectedCase.value = row
  caseExecutionForm.value = {
    execute_time: defaultExecutionTime(),
    steps_result_json: normalizeCaseSteps(row.steps_json).map((item) => ({ ...item, result: 'passed', actual: '' }))
  }
  caseExecutionHistory.value = (await fetchTestCaseExecutions(row.id)).data
  caseExecutionVisible.value = true
}
async function openCaseBug(row) {
  if (!canCreateBugFromCase(row)) return
  bugSourceCase.value = row
  const history = (await fetchTestCaseExecutions(row.id)).data
  const latest = history[0]
  caseBugForm.value = {
    title: row.title,
    bug_type: DEFAULT_BUG_TYPE_KEY,
    severity: '3',
    priority: '3',
    reproduce_steps: buildReproduceText(latest, row),
    actual_result: buildActualText(latest)
  }
  caseBugVisible.value = true
}
async function submitCaseExecution() {
  saving.value = true
  try {
    const currentId = selectedCase.value.id
    await executeTestCase(currentId, { ...caseExecutionForm.value })
    await loadData()
    ElMessage.success('用例执行结果已保存')
    await openNextCaseAfterExecution(currentId, testCases.value)
  } finally {
    saving.value = false
  }
}
async function submitCaseBug() {
  if (!caseBugForm.value.title.trim()) return ElMessage.warning('请填写 Bug 标题')
  saving.value = true
  try {
    await createBugFromTestCase(bugSourceCase.value.id, { ...caseBugForm.value })
    caseBugVisible.value = false
    await loadData()
    ElMessage.success('Bug 已提交')
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
watch(() => route.query.tab, (value) => { activeTab.value = normalizeIterationTab(value) })

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
