# Bug 工作流动作与状态矩阵对齐设计

## 背景

当前默认缺陷工作流以 `pending_handling/待处理` 同时表达“没有处理人”和“已经分派但尚未开始修复”。该节点配置了“认领、指派、转派、变更处理人、确认缺陷类型”等动作，其中“转派”和“变更处理人”在没有处理人的阶段与“指派”语义重复。默认缺陷工作流还没有 `command_type=edit` 动作，导致编辑入口不能由工作流控制。

前端现状并不完全一致：`BugsView.vue` 和 `BugDetailView.vue` 已监听工作流 `command` 并能打开现有编辑界面；`ProjectDetailView.vue` 的 Bug 页签仍固定渲染“编辑”按钮，同时没有监听 Bug 工作流命令。只在后端增加编辑动作会使项目详情出现两个入口，其中工作流入口无法响应。

N-002 将工作项状态按“处理人 × 迭代阶段”拆分为稳定角色：

| 状态角色 | 展示状态 | 处理人 | 迭代阶段 |
|---|---|---|---|
| `unassigned` | 待分派 | 无 | 未开始或进行中 |
| `waiting_iteration` | 待开始 | 有 | 未开始 |
| `active_work` | 修复中 | 有 | 进行中 |

N-004 必须在该矩阵完成后增量调整动作，不能继续以旧 `pending_handling` 节点或中文状态名为判断依据。

## 目标

- Bug 的可用动作由缺陷工作流定义及运行时权限统一决定。
- `unassigned` 只保留“认领”和“指派”两种获得处理人的方式，不提供“转派”和“变更处理人”。
- `waiting_iteration` 与 `active_work` 保留处理人转移能力。
- “编辑”只出现在 `unassigned` 和 `waiting_iteration`，并服从工作流的角色、主操作和更多操作配置。
- 全局 Bug 列表、Bug 详情和项目详情 Bug 页签使用同一编辑命令契约。
- 新环境与服务器已有默认缺陷工作流得到一致结果。

## 非目标

- 不在 N-004 中创建“待分派、待开始、修复中”状态，也不实现 N-002 的创建、指派、迭代启动或迭代移动逻辑。
- 不移除 `waiting_iteration` 或 `active_work` 中的“转派、变更处理人”。
- 不在“修复中、待评审、待验证、已验证、已关闭”等后续状态增加编辑命令。
- 不改变 Bug 编辑表单字段、保存 API 或真正状态流转的审计协议。
- 不按状态显示名称批量修改管理员自定义工作流。

## 方案比较

### 方案一：仅在前端按状态隐藏重复动作

可以快速改变截图中的按钮，但后端仍会返回并允许执行重复动作，其他页面也可能继续展示，无法形成统一权限边界。

### 方案二：重建所有 Bug 工作流

能强制得到统一图，但会覆盖管理员的自定义状态、布局和权限配置，风险不可接受。

### 方案三：按稳定状态角色调整模板并迁移受管默认定义

默认图直接生成正确动作；迁移只处理能够确认属于系统默认或受管默认来源的定义，并以 N-002 稳定角色定位状态。前端仅补齐项目详情的工作流命令接入，不改变通用动作组件。

采用方案三。

## 动作矩阵

| 状态角色 | 指派 | 转派 | 变更处理人 | 编辑 |
|---|---:|---:|---:|---:|
| `unassigned` | 保留 | 移除 | 移除 | 增加 |
| `waiting_iteration` | 不提供 | 保留 | 保留 | 增加 |
| `active_work` | 不提供 | 保留 | 保留 | 不提供 |
| 评审、验证及终态 | 沿用 N-002 后既有配置 | 沿用既有配置 | 沿用既有配置 | 不提供 |

“认领”仍保留在 `unassigned`，与“指派”的权限边界不同：认领由符合条件的项目成员把自己设为处理人，指派由项目管理身份选择处理人。两者不是重复动作。

## 后端设计

### 默认缺陷模板

修改 `backend/app/services/default_workflow_template_service.py` 中 N-002 改造后的 `_bug_graph()`：

- 在 `unassigned` 状态保留 `claim`、`assign`，不生成 `transfer`、`change_handler`。
- 在 `unassigned` 增加 `action_key=edit`、`command_type=edit` 的同状态命令动作。
- 在 `waiting_iteration` 增加同一编辑命令，并保留该状态的 `transfer`、`change_handler`。
- 保持 `active_work` 的 `transfer`、`change_handler`，但不增加 `edit`。
- 编辑动作使用与需求、任务默认模板一致的创建者权限语义，列表默认放入“更多操作”；最终角色 ID 仍由模板角色解析逻辑生成。

编辑是本地界面命令，不调用工作流执行接口、不改变状态、不新增流转历史。

### 既有定义迁移

仅修改模板代码不足以覆盖服务器数据，因为 `ensure_default_workflow_templates()` 对既有定义不会重建完整图。新增可复用的缺陷动作对齐函数，并由 Alembic 数据迁移调用：

- 前置检查 N-002 稳定状态角色已存在；缺失时直接失败并给出明确错误，避免退回名称猜测。
- 仅选择系统默认 `bug.default` 以及项目实际使用的、可确认由默认缺陷模板派生的受管定义；跳过无法确认来源的自定义定义。
- 在 `unassigned` 停用或删除尚未产生业务历史的 `transfer`、`change_handler` 配置；若模型采用软停用约定，则保持记录并设置 `enabled=False`。
- 幂等地为 `unassigned`、`waiting_iteration` 创建或更新 `edit` 命令；重复执行不得产生重复动作。
- 确认 `waiting_iteration`、`active_work` 的处理人转移动作仍启用，不更改评审、验证和终态动作。
- `downgrade()` 不猜测恢复管理员配置；保留已经对齐的动作并在迁移注释中说明不可逆原因。

迁移选择范围必须复用 N-002 对“受管默认工作流”的识别结果，避免 N-004 另建一套来源判断。

## 前端设计

### 已具备能力的页面

- `frontend/src/views/BugsView.vue` 已通过 `handleWorkflowCommand(row, { commandType })` 打开列表编辑弹窗。
- `frontend/src/views/BugDetailView.vue` 已通过 `handleWorkflowCommand({ commandType })` 进入详情编辑模式。

这两个页面只需要回归测试，不修改命令处理逻辑。

### 项目详情 Bug 页签

修改 `frontend/src/views/ProjectDetailView.vue`：

- 删除直接调用 `openBugEdit(row)` 的固定编辑按钮。
- 为 Bug 的 `WorkflowActionButtons` 增加 `@command="handleBugWorkflowCommand(row, $event)"`。
- 新增命令处理函数，仅在 `commandType === 'edit'` 时调用现有 `openBugEdit(row)`。
- 保留 `@executed="refreshAfterMutation"` 处理真实工作流流转后的刷新。
- 保留删除按钮、批量指派、编辑弹窗及保存逻辑。

工作流未返回 `edit` 时不显示编辑入口；配置为主操作或更多操作时，由 `WorkflowActionButtons` 原有分组逻辑决定位置。

## 兼容与顺序

实施顺序固定为：

1. 完成 N-002 的稳定状态角色、状态矩阵和既有工作流迁移。
2. 在 N-002 结果上修改默认缺陷模板及动作对齐迁移。
3. 接入项目详情 Bug 编辑命令。
4. 执行后端动作矩阵、迁移幂等性和三个前端入口的回归验证。

若 N-002 尚未落地，N-004 不得通过旧 `pending_handling` 或“待处理”名称提前实施，否则后续状态拆分会再次使动作落错节点。

## 测试设计

- 默认模板测试：断言 `unassigned` 只有 `assign` 而没有 `transfer/change_handler`，`unassigned` 和 `waiting_iteration` 有 `edit`，`active_work` 没有 `edit` 且保留处理人转移动作。
- 运行时权限测试：创建者能在前两个状态看到编辑；普通成员和无权限用户不能因前端入口绕过后端动作过滤。
- 迁移测试：覆盖新建默认图、服务器既有默认图、重复执行、缺少 N-002 状态角色和自定义图不被修改。
- 前端契约测试：项目详情不再固定显示 Bug 编辑按钮，工作流命令能打开现有弹窗；全局列表和详情页已有命令处理保持可用。
- 浏览器验收：分别验证“编辑为主操作”“编辑在更多中”“当前状态无编辑动作”，并确认点击编辑不会发送工作流 transition 请求。
