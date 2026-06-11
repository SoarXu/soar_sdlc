<template>
  <section>
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
              <div class="project-history-line">
                <span class="project-history-index">{{ index + 1 }}</span>
                <span>{{ formatDateTime(item.time) }}，由 {{ item.actor }} {{ item.actionLabel }}。</span>
                <button
                  v-if="item.type === 'audit'"
                  class="project-history-toggle"
                  type="button"
                  @click="toggleHistory(item.key)"
                >
                  {{ expandedHistory[item.key] ? '-' : '+' }}
                </button>
              </div>
              <div v-if="item.type === 'audit' && expandedHistory[item.key]" class="project-history-detail">
                <p v-for="change in item.changes" :key="change.field">
                  修改了 <strong>{{ projectFieldLabel(change.field) }}</strong>，旧值为 "{{ displayHistoryValue(change.oldValue) }}"，新值为 "{{ displayHistoryValue(change.newValue) }}"。
                </p>
              </div>
            </div>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'iterations'">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openIterationCreate">新增迭代</el-button></div>
        <el-table :data="projectIterations" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="name" label="迭代名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column prop="start_date" label="开始日期" width="130" />
          <el-table-column prop="end_date" label="结束日期" width="130" />
          <el-table-column label="状态" width="120"><template #default="{ row }">{{ iterationStatusLabel(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }"><el-button link type="primary" @click="openIterationEdit(row)">编辑</el-button><el-popconfirm title="确认删除该迭代？" @confirm="removeIteration(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else-if="activeTab === 'requirements'">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openRequirementCreate">新增需求</el-button></div>
        <el-table :data="projectRequirements" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="需求标题" min-width="180" show-overflow-tooltip>
            <template #default="{ row }"><router-link class="table-link" :to="`/requirements/${row.id}`">{{ row.title }}</router-link></template>
          </el-table-column>
          <el-table-column label="迭代" width="160"><template #default="{ row }">{{ labelById(projectIterations, row.iteration_id) }}</template></el-table-column>
          <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column label="优先级" width="100"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
          <el-table-column label="评审状态" width="120"><template #default="{ row }">{{ reviewStatusLabel(row.review_status) }}</template></el-table-column>
          <el-table-column label="状态" width="100"><template #default="{ row }">{{ requirementStatusLabel(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openRequirementEdit(row)">编辑</el-button>
              <el-button v-if="canActivateRequirement(row)" link type="warning" @click="activateRequirementRow(row.id)">激活</el-button>
              <el-button v-if="row.status === 'active'" link type="danger" @click="openRequirementClose(row)">关闭</el-button>
              <el-button link type="success" @click="openGenerate(row)">生成任务</el-button>
              <el-popconfirm title="确认删除该需求？" @confirm="removeRequirement(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else-if="activeTab === 'tasks'">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openTaskCreate">新增任务</el-button></div>
        <el-table :data="projectTasks" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="任务标题" min-width="180" show-overflow-tooltip>
            <template #default="{ row }"><router-link class="table-link" :to="`/tasks/${row.id}`">{{ row.title }}</router-link></template>
          </el-table-column>
          <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(projectRequirements, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column prop="actual_hours" label="实际工时" width="110" />
          <el-table-column prop="due_date" label="截止日期" width="130" />
          <el-table-column label="状态" width="110"><template #default="{ row }">{{ taskStatusLabel(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }"><el-button link type="primary" @click="openTaskEdit(row)">编辑</el-button><el-button v-if="canActivateTask(row)" link type="warning" @click="activateTaskRow(row.id)">激活</el-button><el-button v-if="row.status !== 'closed'" link type="danger" @click="openTaskClose(row)">关闭</el-button><el-popconfirm title="确认删除该任务？" @confirm="removeTask(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else-if="activeTab === 'tests'">
        <el-tabs v-model="testTab">
          <el-tab-pane label="测试用例" name="cases">
            <div class="project-tab-toolbar"><el-button type="primary" @click="openCaseCreate">新增用例</el-button></div>
            <el-table :data="projectTestCases" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="title" label="用例标题" min-width="180" show-overflow-tooltip />
              <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(projectRequirements, row.requirement_id, 'title') }}</template></el-table-column>
              <el-table-column label="默认测试人" width="140"><template #default="{ row }">{{ userLabel(users, row.default_tester_id) }}</template></el-table-column>
              <el-table-column prop="priority" label="优先级" width="100" />
              <el-table-column label="状态" width="100"><template #default="{ row }">{{ testCaseStatusLabel(row.status) }}</template></el-table-column>
              <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openCaseEdit(row)">编辑</el-button><el-popconfirm title="确认删除该用例？" @confirm="removeCase(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template></el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="测试单" name="runs">
            <div class="project-tab-toolbar"><el-button type="primary" @click="openRunCreate">新增测试单</el-button></div>
            <el-table :data="projectTestRuns" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="name" label="测试单名称" min-width="180" show-overflow-tooltip />
              <el-table-column label="迭代" width="160"><template #default="{ row }">{{ labelById(projectIterations, row.iteration_id) }}</template></el-table-column>
              <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.test_owner_id) }}</template></el-table-column>
              <el-table-column label="状态" width="110"><template #default="{ row }">{{ testRunStatusLabel(row.status) }}</template></el-table-column>
              <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openRunEdit(row)">编辑</el-button><el-popconfirm title="确认删除该测试单？" @confirm="removeRun(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template></el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>

      <template v-else-if="activeTab === 'bugs'">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openBugCreate">新增 Bug</el-button></div>
        <el-table :data="projectBugs" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="title" label="Bug 标题" min-width="180" show-overflow-tooltip />
          <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(projectRequirements, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column label="任务" width="180"><template #default="{ row }">{{ labelById(projectTasks, row.task_id, 'title') }}</template></el-table-column>
          <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column prop="severity" label="严重程度" width="110" />
          <el-table-column label="状态" width="120"><template #default="{ row }">{{ bugStatusLabel(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="openBugEdit(row)">编辑</el-button><el-popconfirm title="确认删除该 Bug？" @confirm="removeBug(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template></el-table-column>
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

    <el-dialog v-model="requirementDialogVisible" :title="editingRequirementId ? '编辑需求' : '新增需求'" width="640px">
      <el-form label-position="top">
        <el-form-item label="需求标题" required><el-input v-model="requirementForm.title" /></el-form-item>
        <div class="form-grid"><el-form-item label="迭代"><el-select v-model="requirementForm.iteration_id" clearable filterable><el-option v-for="iteration in projectIterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item><el-form-item label="负责人"><el-select v-model="requirementForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="提出人"><el-select v-model="requirementForm.proposer_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="类型"><el-input v-model="requirementForm.requirement_type" /></el-form-item><el-form-item label="优先级"><el-select v-model="requirementForm.priority" class="priority-select"><template #prefix><RequirementPriorityBadge :value="requirementForm.priority" /></template><el-option v-for="option in requirementPriorityOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item><el-form-item label="评审状态"><el-select v-model="requirementForm.review_status"><el-option label="无需评审" value="not_required" /><el-option label="待评审" value="pending" /><el-option label="已通过" value="approved" /></el-select></el-form-item></div>
        <el-form-item label="需求描述"><el-input v-model="requirementForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="requirementForm.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="requirementDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirement">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="generateVisible" title="从需求生成任务" width="480px">
      <el-form label-position="top"><el-form-item label="任务标题" required><el-input v-model="generateForm.title" /></el-form-item><el-form-item label="任务类型"><el-input v-model="generateForm.task_type" /></el-form-item><el-form-item label="描述"><el-input v-model="generateForm.description" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="generateVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitGenerateTask">生成</el-button></template>
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
        <div class="form-grid"><el-form-item label="需求"><el-select v-model="taskForm.requirement_id" clearable filterable><el-option v-for="requirement in projectRequirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item><el-form-item label="负责人"><el-select v-model="taskForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="类型"><el-input v-model="taskForm.task_type" /></el-form-item><el-form-item label="优先级"><el-select v-model="taskForm.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item><el-form-item label="预计工时"><el-input-number v-model="taskForm.estimated_hours" :min="0" /></el-form-item><el-form-item label="实际工时"><el-input-number v-model="taskForm.actual_hours" :min="0" /></el-form-item><el-form-item label="截止日期"><el-date-picker v-model="taskForm.due_date" value-format="YYYY-MM-DD" type="date" /></el-form-item><el-form-item label="状态"><el-select v-model="taskForm.status"><el-option label="待办" value="todo" /><el-option label="进行中" value="doing" /><el-option label="完成" value="done" /><el-option label="关闭" value="closed" /></el-select></el-form-item></div>
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

    <el-dialog v-model="caseDialogVisible" :title="editingCaseId ? '编辑用例' : '新增用例'" width="620px">
      <el-form label-position="top"><el-form-item label="用例标题" required><el-input v-model="caseForm.title" /></el-form-item><div class="form-grid"><el-form-item label="需求"><el-select v-model="caseForm.requirement_id" clearable filterable><el-option v-for="requirement in projectRequirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item><el-form-item label="默认测试人"><el-select v-model="caseForm.default_tester_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="类型"><el-input v-model="caseForm.case_type" /></el-form-item><el-form-item label="优先级"><el-select v-model="caseForm.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item><el-form-item label="状态"><el-select v-model="caseForm.status"><el-option label="启用" value="active" /><el-option label="停用" value="inactive" /></el-select></el-form-item></div><el-form-item label="前置条件"><el-input v-model="caseForm.precondition" type="textarea" :rows="2" /></el-form-item><el-form-item label="预期结果"><el-input v-model="caseForm.expected_result" type="textarea" :rows="2" /></el-form-item></el-form>
      <template #footer><el-button @click="caseDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCase">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="runDialogVisible" :title="editingRunId ? '编辑测试单' : '新增测试单'" width="560px">
      <el-form label-position="top"><el-form-item label="测试单名称" required><el-input v-model="runForm.name" /></el-form-item><div class="form-grid"><el-form-item label="迭代"><el-select v-model="runForm.iteration_id" clearable filterable><el-option v-for="iteration in projectIterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item><el-form-item label="测试负责人"><el-select v-model="runForm.test_owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="状态"><el-select v-model="runForm.status"><el-option label="规划中" value="planning" /><el-option label="执行中" value="running" /><el-option label="完成" value="finished" /></el-select></el-form-item></div><el-form-item label="备注"><el-input v-model="runForm.remark" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="runDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRun">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="bugDialogVisible" :title="editingBugId ? '编辑 Bug' : '新增 Bug'" width="700px">
      <el-form label-position="top"><el-form-item label="Bug 标题" required><el-input v-model="bugForm.title" /></el-form-item><div class="form-grid"><el-form-item label="需求"><el-select v-model="bugForm.requirement_id" clearable filterable><el-option v-for="requirement in projectRequirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item><el-form-item label="任务"><el-select v-model="bugForm.task_id" clearable filterable><el-option v-for="task in projectTasks" :key="task.id" :label="task.title" :value="task.id" /></el-select></el-form-item><el-form-item label="来源用例"><el-select v-model="bugForm.test_case_id" clearable filterable><el-option v-for="item in projectTestCases" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item><el-form-item label="来源测试单"><el-select v-model="bugForm.test_run_id" clearable filterable><el-option v-for="run in projectTestRuns" :key="run.id" :label="run.name" :value="run.id" /></el-select></el-form-item><el-form-item label="负责人"><el-select v-model="bugForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="提出人"><el-select v-model="bugForm.reporter_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item><el-form-item label="严重程度"><el-select v-model="bugForm.severity"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item><el-form-item label="优先级"><el-select v-model="bugForm.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item><el-form-item label="状态"><el-select v-model="bugForm.status"><el-option label="待修复" value="open" /><el-option label="修复中" value="fixing" /><el-option label="待验证" value="verifying" /><el-option label="已关闭" value="closed" /><el-option label="重新打开" value="reopened" /></el-select></el-form-item></div><el-form-item label="复现步骤"><el-input v-model="bugForm.reproduce_steps" type="textarea" :rows="3" /></el-form-item><el-form-item label="期望结果"><el-input v-model="bugForm.expected_result" type="textarea" :rows="2" /></el-form-item><el-form-item label="实际结果"><el-input v-model="bugForm.actual_result" type="textarea" :rows="2" /></el-form-item></el-form>
      <template #footer><el-button @click="bugDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitBug">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { createBug, deleteBug, fetchBugs, updateBug } from '../api/bugs'
import { createIteration, deleteIteration, fetchIterations, updateIteration } from '../api/iterations'
import { fetchPrograms } from '../api/programs'
import { fetchProject, fetchProjectAuditLogs, fetchProjectStatusOperations } from '../api/projects'
import { activateRequirement, closeRequirement, createRequirement, deleteRequirement, fetchRequirements, generateTask, updateRequirement } from '../api/requirements'
import { activateTask, closeTask, createTask, deleteTask, fetchTasks, updateTask } from '../api/tasks'
import { createTestCase, deleteTestCase, fetchTestCases, updateTestCase } from '../api/testCases'
import { createTestRun, deleteTestRun, fetchTestRuns, updateTestRun } from '../api/testRuns'
import { fetchUsers } from '../api/users'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const activeTab = ref(normalizeProjectTab(route.query.tab))
const testTab = ref('cases')
const project = ref({})
const programs = ref([])
const users = ref([])
const iterations = ref([])
const requirements = ref([])
const tasks = ref([])
const testCases = ref([])
const testRuns = ref([])
const bugs = ref([])
const projectAuditLogs = ref([])
const projectStatusOperations = ref([])
const expandedHistory = reactive({})

const iterationDialogVisible = ref(false), requirementDialogVisible = ref(false), generateVisible = ref(false), closeRequirementVisible = ref(false), taskDialogVisible = ref(false), closeTaskVisible = ref(false)
const caseDialogVisible = ref(false), runDialogVisible = ref(false), bugDialogVisible = ref(false)
const editingIterationId = ref(null), editingRequirementId = ref(null), generatingRequirementId = ref(null), closingRequirementId = ref(null), editingTaskId = ref(null)
const closingTaskId = ref(null)
const editingCaseId = ref(null), editingRunId = ref(null), editingBugId = ref(null)

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
  { label: '运维中', value: 'maintenance' },
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
const testCaseStatusOptions = [
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' }
]
const testRunStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '执行中', value: 'running' },
  { label: '完成', value: 'finished' }
]
const bugStatusOptions = [
  { label: '待修复', value: 'open' },
  { label: '修复中', value: 'fixing' },
  { label: '待验证', value: 'verifying' },
  { label: '已关闭', value: 'closed' },
  { label: '重新打开', value: 'reopened' }
]

const projectIterations = computed(() => iterations.value.filter((item) => (item.project_ids || []).includes(projectId.value)))
const projectRequirements = computed(() => requirements.value.filter((item) => item.project_id === projectId.value))
const projectTasks = computed(() => tasks.value.filter((item) => item.project_id === projectId.value))
const projectTestCases = computed(() => testCases.value.filter((item) => item.project_id === projectId.value))
const projectTestRuns = computed(() => testRuns.value.filter((item) => item.project_id === projectId.value))
const projectBugs = computed(() => bugs.value.filter((item) => item.project_id === projectId.value))
const activeTabLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label || '')
const projectEndDateLabel = computed(() => project.value.is_long_term ? '长期' : project.value.end_date || '未设置结束')
const metrics = computed(() => [
  { key: 'iterations', label: '迭代', value: projectIterations.value.length },
  { key: 'requirements', label: '需求', value: projectRequirements.value.length },
  { key: 'tasks', label: '任务', value: projectTasks.value.length },
  { key: 'tests', label: '测试', value: projectTestCases.value.length + projectTestRuns.value.length },
  { key: 'bugs', label: 'Bug', value: projectBugs.value.length }
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

const iterationForm = reactive({ project_ids: [], name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' })
const requirementForm = reactive({ project_id: null, iteration_id: null, title: '', requirement_type: '', priority: '3', owner_id: null, proposer_id: null, status: 'draft', review_status: 'not_required', description: '', acceptance_criteria: '', source_reviewed: false })
const generateForm = reactive({ title: '', task_type: '', description: '' })
const closeRequirementForm = reactive({ reason: '', remark: '' })
const taskForm = reactive({ project_id: null, requirement_id: null, title: '', task_type: '', priority: 'medium', owner_id: null, estimated_hours: null, actual_hours: null, due_date: null, status: 'todo', description: '' })
const closeTaskForm = reactive({ reason: '', remark: '' })
const caseForm = reactive({ project_id: null, requirement_id: null, title: '', case_type: '', priority: 'medium', default_tester_id: null, precondition: '', expected_result: '', status: 'active' })
const runForm = reactive({ project_id: null, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' })
const bugForm = reactive({ project_id: null, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', severity: 'medium', priority: 'medium', owner_id: null, reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '', status: 'open' })

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function normalizeProjectTab(value) {
  return ['overview', 'iterations', 'requirements', 'tasks', 'tests', 'bugs', 'members', 'settings'].includes(value) ? value : 'overview'
}
function setActiveTab(key) {
  activeTab.value = key
  router.replace({ name: 'project-detail', params: { id: projectId.value }, query: { ...route.query, tab: key } })
}
function projectStatusLabel(value) { return optionLabel(projectStatusOptions, value) }
function iterationStatusLabel(value) { return optionLabel(iterationStatusOptions, value) }
function normalizeRequirementPriority(value) { return legacyRequirementPriorityValues[value] || value || '3' }
function requirementStatusLabel(value) { return optionLabel(requirementStatusOptions, value) }
function reviewStatusLabel(value) { return optionLabel(reviewStatusOptions, value) }
function taskStatusLabel(value) { return optionLabel(taskStatusOptions, value) }
function testCaseStatusLabel(value) { return optionLabel(testCaseStatusOptions, value) }
function testRunStatusLabel(value) { return optionLabel(testRunStatusOptions, value) }
function bugStatusLabel(value) { return optionLabel(bugStatusOptions, value) }
function operationActionLabel(value) { return optionLabel([{ label: '启动', value: 'start' }, { label: '挂起', value: 'suspend' }, { label: '关闭', value: 'close' }, { label: '激活', value: 'activate' }, { label: '转运维', value: 'move_to_maintenance' }], value) }
function canActivateRequirement(row) { return ['draft', 'closed'].includes(row.status) }
function canActivateTask(row) { return ['todo', 'closed'].includes(row.status) }
function apiErrorMessage(error, fallback) { return error?.response?.data?.detail || fallback }
function showActionError(error, fallback) { ElMessageBox.alert(apiErrorMessage(error, fallback), '提示', { type: 'warning' }) }
function toggleHistory(key) { expandedHistory[key] = !expandedHistory[key] }
function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function displayHistoryValue(value) { return value === null || value === undefined || value === '' ? '-' : value }
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
function resetIterationForm() { Object.assign(iterationForm, { project_ids: [projectId.value], name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' }) }
function resetRequirementForm() { Object.assign(requirementForm, { project_id: projectId.value, iteration_id: null, title: '', requirement_type: '', priority: '3', owner_id: project.value.owner_id || null, proposer_id: null, status: 'draft', review_status: 'not_required', description: '', acceptance_criteria: '', source_reviewed: false }) }
function resetTaskForm() { Object.assign(taskForm, { project_id: projectId.value, requirement_id: null, title: '', task_type: '', priority: 'medium', owner_id: null, estimated_hours: null, actual_hours: null, due_date: null, status: 'todo', description: '' }) }
function resetCaseForm() { Object.assign(caseForm, { project_id: projectId.value, requirement_id: null, title: '', case_type: '', priority: 'medium', default_tester_id: null, precondition: '', expected_result: '', status: 'active' }) }
function resetRunForm() { Object.assign(runForm, { project_id: projectId.value, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' }) }
function resetBugForm() { Object.assign(bugForm, { project_id: projectId.value, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', severity: 'medium', priority: 'medium', owner_id: null, reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '', status: 'open' }) }

function openIterationCreate() { editingIterationId.value = null; resetIterationForm(); iterationDialogVisible.value = true }
function openIterationEdit(row) { editingIterationId.value = row.id; Object.assign(iterationForm, { ...row, project_ids: row.project_ids || [], goal: row.goal || '' }); iterationDialogVisible.value = true }
function openRequirementCreate() { editingRequirementId.value = null; resetRequirementForm(); requirementDialogVisible.value = true }
function openRequirementEdit(row) { editingRequirementId.value = row.id; Object.assign(requirementForm, { ...row, priority: normalizeRequirementPriority(row.priority), requirement_type: row.requirement_type || '', description: row.description || '', acceptance_criteria: row.acceptance_criteria || '' }); requirementDialogVisible.value = true }
function openGenerate(row) { generatingRequirementId.value = row.id; generateForm.title = row.title; generateForm.task_type = 'development'; generateForm.description = ''; generateVisible.value = true }
function openRequirementClose(row) { closingRequirementId.value = row.id; Object.assign(closeRequirementForm, { reason: '', remark: '' }); closeRequirementVisible.value = true }
function openTaskCreate() { editingTaskId.value = null; resetTaskForm(); taskDialogVisible.value = true }
function openTaskEdit(row) { editingTaskId.value = row.id; Object.assign(taskForm, { ...row, task_type: row.task_type || '', description: row.description || '' }); taskDialogVisible.value = true }
function openTaskClose(row) { closingTaskId.value = row.id; Object.assign(closeTaskForm, { reason: '', remark: '' }); closeTaskVisible.value = true }
function openCaseCreate() { editingCaseId.value = null; resetCaseForm(); caseDialogVisible.value = true }
function openCaseEdit(row) { editingCaseId.value = row.id; Object.assign(caseForm, { ...row, case_type: row.case_type || '', precondition: row.precondition || '', expected_result: row.expected_result || '' }); caseDialogVisible.value = true }
function openRunCreate() { editingRunId.value = null; resetRunForm(); runDialogVisible.value = true }
function openRunEdit(row) { editingRunId.value = row.id; Object.assign(runForm, { ...row, remark: row.remark || '' }); runDialogVisible.value = true }
function openBugCreate() { editingBugId.value = null; resetBugForm(); bugDialogVisible.value = true }
function openBugEdit(row) { editingBugId.value = row.id; Object.assign(bugForm, { ...row, reproduce_steps: row.reproduce_steps || '', expected_result: row.expected_result || '', actual_result: row.actual_result || '' }); bugDialogVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [projectRes, programRes, userRes, iterationRes, requirementRes, taskRes, caseRes, runRes, bugRes, auditRes, statusRes] = await Promise.all([
      fetchProject(projectId.value),
      fetchPrograms(),
      fetchUsers(),
      fetchIterations({ project_id: projectId.value }),
      fetchRequirements(),
      fetchTasks(),
      fetchTestCases(),
      fetchTestRuns(),
      fetchBugs(),
      fetchProjectAuditLogs(projectId.value),
      fetchProjectStatusOperations(projectId.value)
    ])
    project.value = projectRes.data; programs.value = programRes.data; users.value = userRes.data; iterations.value = iterationRes.data
    requirements.value = requirementRes.data; tasks.value = taskRes.data; testCases.value = caseRes.data; testRuns.value = runRes.data; bugs.value = bugRes.data
    projectAuditLogs.value = auditRes.data; projectStatusOperations.value = statusRes.data
  } catch {
    ElMessage.error('项目详情加载失败')
  } finally {
    loading.value = false
  }
}

async function submitIteration() { if (!iterationForm.name.trim()) return ElMessage.warning('请填写迭代名称'); saving.value = true; try { const payload = { ...iterationForm, project_ids: iterationForm.project_ids.length ? iterationForm.project_ids : [projectId.value], owner_id: iterationForm.owner_id || null }; if (editingIterationId.value) await updateIteration(editingIterationId.value, payload); else await createIteration(payload); iterationDialogVisible.value = false; await loadData() } finally { saving.value = false } }
async function submitRequirement() { if (!requirementForm.title.trim()) return ElMessage.warning('请填写需求标题'); saving.value = true; try { const { status: _status, ...formData } = requirementForm; const payload = { ...formData, project_id: projectId.value, iteration_id: requirementForm.iteration_id || null, owner_id: requirementForm.owner_id || null, proposer_id: requirementForm.proposer_id || null }; if (editingRequirementId.value) await updateRequirement(editingRequirementId.value, payload); else await createRequirement(payload); requirementDialogVisible.value = false; await loadData() } finally { saving.value = false } }
async function activateRequirementRow(id) { try { await activateRequirement(id); await loadData(); ElMessage.success('需求已激活，关联任务已进入进行中') } catch (error) { showActionError(error, '需求激活失败') } }
async function submitGenerateTask() { if (!generateForm.title.trim()) return ElMessage.warning('请填写任务标题'); saving.value = true; try { await generateTask(generatingRequirementId.value, { ...generateForm }); generateVisible.value = false; await loadData(); ElMessage.success('任务已生成') } finally { saving.value = false } }
async function submitRequirementClose() {
  if (!closeRequirementForm.reason) return ElMessage.warning('请选择关闭原因')
  saving.value = true
  try {
    await closeRequirement(closingRequirementId.value, { ...closeRequirementForm })
    closeRequirementVisible.value = false
    await loadData()
    ElMessage.success('需求已关闭')
  } finally {
    saving.value = false
  }
}
async function submitTask() { if (!taskForm.title.trim()) return ElMessage.warning('请填写任务标题'); saving.value = true; try { const payload = { ...taskForm, project_id: projectId.value, requirement_id: taskForm.requirement_id || null, owner_id: taskForm.owner_id || null }; if (editingTaskId.value) await updateTask(editingTaskId.value, payload); else await createTask(payload); taskDialogVisible.value = false; await loadData() } finally { saving.value = false } }
async function activateTaskRow(id) { try { await activateTask(id); await loadData(); ElMessage.success('任务已激活') } catch (error) { showActionError(error, '任务激活失败') } }
async function submitTaskClose() { if (!closeTaskForm.reason) return ElMessage.warning('请选择关闭原因'); saving.value = true; try { await closeTask(closingTaskId.value, { ...closeTaskForm }); closeTaskVisible.value = false; await loadData(); ElMessage.success('任务已关闭') } catch (error) { showActionError(error, '任务关闭失败') } finally { saving.value = false } }
async function submitCase() { if (!caseForm.title.trim()) return ElMessage.warning('请填写用例标题'); saving.value = true; try { const payload = { ...caseForm, project_id: projectId.value, requirement_id: caseForm.requirement_id || null, default_tester_id: caseForm.default_tester_id || null }; if (editingCaseId.value) await updateTestCase(editingCaseId.value, payload); else await createTestCase(payload); caseDialogVisible.value = false; await loadData() } finally { saving.value = false } }
async function submitRun() { if (!runForm.name.trim()) return ElMessage.warning('请填写测试单名称'); saving.value = true; try { const payload = { ...runForm, project_id: projectId.value, iteration_id: runForm.iteration_id || null, test_owner_id: runForm.test_owner_id || null }; if (editingRunId.value) await updateTestRun(editingRunId.value, payload); else await createTestRun(payload); runDialogVisible.value = false; await loadData() } finally { saving.value = false } }
async function submitBug() { if (!bugForm.title.trim()) return ElMessage.warning('请填写 Bug 标题'); saving.value = true; try { const payload = { ...bugForm, project_id: projectId.value, requirement_id: bugForm.requirement_id || null, task_id: bugForm.task_id || null, test_case_id: bugForm.test_case_id || null, test_run_id: bugForm.test_run_id || null, owner_id: bugForm.owner_id || null, reporter_id: bugForm.reporter_id || null }; if (editingBugId.value) await updateBug(editingBugId.value, payload); else await createBug(payload); bugDialogVisible.value = false; await loadData() } finally { saving.value = false } }
async function removeIteration(id) { await deleteIteration(id); await loadData() }
async function removeRequirement(id) { await deleteRequirement(id); await loadData() }
async function removeTask(id) { await deleteTask(id); await loadData() }
async function removeCase(id) { await deleteTestCase(id); await loadData() }
async function removeRun(id) { await deleteTestRun(id); await loadData() }
async function removeBug(id) { await deleteBug(id); await loadData() }

onMounted(loadData)
watch(() => route.query.tab, (value) => { activeTab.value = normalizeProjectTab(value) })
</script>
