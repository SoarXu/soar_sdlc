# 工作流 PRD 实施完成报告

## 1. 报告结论

`docs/prd/2026-07-16-workflow-end-to-end-functional-prd.md` 中 FR-1 至 FR-13 的已确认范围已完成实现，并通过后端全量测试、前端全量测试、生产构建、数据库迁移往返和独立迁移审计。

本次完成的核心结果：

- 工作流方案支持创建空白方案，或从统一来源列表选择系统标准方案、已有完整方案进行整套复制。
- 复制结果完全独立，不保存来源关系，不复用状态、流转或方案数据库 ID。
- 方案使用草稿、已启用、已停用三态生命周期，并具备启用校验、项目绑定限制和停用保护。
- 需求、任务、Bug、项目、迭代使用不可变状态节点 ID 作为状态身份，旧状态字符串列已通过迁移删除。
- 流程图按状态 ID 增量保存，流转边、初始状态和条件路由均使用状态 ID。
- 新业务对象始终进入工作流定义的唯一初始状态，是否已指定负责人不再改变初始状态。
- 页面、工作台、详情、动作选择和历史记录统一展示后端返回的中文 `status_name` 或状态名称快照。

## 2. FR 追溯矩阵

| 需求 | 实现证据 | 测试证据 | 状态 | 残余风险 |
|---|---|---|---|---|
| FR-1 新建方案入口 | `frontend/src/views/WorkflowView.vue`、`frontend/src/utils/workflowSchemeCreation.js` | `workflowSchemeCreation.test.mjs`、浏览器桌面/移动验收 | 完成 | 无 |
| FR-2 创建空白方案 | `assignee_rule_config_service.create_config` 创建三类空定义和草稿方案 | `test_blank_creation_builds_three_empty_draft_definitions` | 完成 | 空白方案必须配置完成后才能启用，符合设计 |
| FR-3 从模板创建 | 统一 `template-sources` 接口和 `creation_mode=template` 契约 | `test_template_sources_unify_system_and_existing_schemes`、浏览器从系统和已有方案各创建一次 | 完成 | 缺少任一三类启用定义的历史方案会被排除；当前不按方案生命周期过滤 |
| FR-4 模板复制范围 | `_clone_graph` 内 `transition.handler_rule` 随图深复制、无独立同步或双写；配置 JSON 深复制 | `test_system_and_existing_scheme_templates_create_independent_full_copies` | 完成 | 仅复制本 PRD 定义的需求、任务、Bug 三类图 |
| FR-5 复制独立性 | 状态、流转、定义均生成新 ID，不保存 lineage 字段 | 独立 ID 集合断言及浏览器后 API 数据核对 | 完成 | 无来源追溯是明确需求，不是缺失 |
| FR-6 方案生命周期 | `lifecycle_status`、`enable/disable` 端点、项目可选方案过滤 | `test_workflow_scheme_lifecycle_guards_project_binding_and_disable` | 完成 | 已启用方案编辑策略、停用恢复仍待产品确认 |
| FR-7 方案停用保护 | 停用前统计关联项目并返回项目数量和入口参数 | 生命周期 API 测试及前端错误反馈测试 | 完成 | 项目清单入口依赖现有方案详情关联表 |
| FR-8 状态节点唯一标识 | `workflow_states.id`、设计器正数 ID/负数临时 ID、无可编辑状态编码 | `test_graph_save_remaps_temporary_ids_and_preserves_ids_when_state_is_renamed`、`workflowStateIdentity.test.mjs` | 完成 | `status_key` 已于 2026-07-17 收尾迁移物理删除 |
| FR-9 业务对象关联状态节点 | 三类模型强制非空 `workflow_definition_id/current_state_id`；迁移删除旧 `status` 列 | 仓库守卫、模型元数据测试、全量 API 测试、迁移审计 | 完成 | `20260716_001` 完成需求、任务、Bug 状态 ID 回填；`20260717_001` 完成项目、迭代状态 ID 回填 |
| FR-10 流转边关联状态节点 | 图保存和运行时使用 `from_state_id/to_state_id`；人工路由只接受 `selected_target_state_id` | 图 API 测试、运行时 ID 流转测试、仓库守卫 | 完成 | 项目、迭代已完成 ID 化，`from_status/to_status` 已物理删除 |
| FR-11 状态节点增量保存 | `_persist_graph` 按 ID 更新、新增、禁用或删除；引用保护 | 工作流图保存、重命名、引用删除保护测试 | 完成 | 大规模图的并发编辑冲突策略未在本 PRD 定义 |
| FR-12 工作流初始状态 | `workflow_definitions.initial_state_id`，启用和保存时校验归属、唯一性、启用状态 | 初始状态模型、图保存和方案启用测试 | 完成 | 空白草稿允许暂时没有初始状态，启用时强制校验 |
| FR-13 创建后初始状态 | `initial_workflow_values` 只写定义 ID 和初始状态 ID；负责人不参与状态选择 | `test_new_work_items_always_enter_definition_initial_state_regardless_of_owner` 等 | 完成 | 自动开始处理必须未来通过自动流转配置实现 |

## 3. 验收标准完成情况

| 编号 | 验收项 | 结果 | 证据摘要 |
|---:|---|---|---|
| 1 | 明确选择空白或模板创建 | 通过 | 创建页单选模式及前端测试 |
| 2 | 同一来源列表包含系统和已有方案 | 通过 | 分组来源接口、浏览器验收 |
| 3 | 三类完整工作流及配置均复制 | 通过 | 三图、状态、流转、处理人规则和 JSON 配置等值测试 |
| 4 | 副本与来源互不影响 | 通过 | 所有定义、状态、流转 ID 不相交 |
| 5 | 不记录、不展示复制来源 | 通过 | 响应和数据库模型无来源 lineage 字段 |
| 6 | 新方案均为草稿且不可绑定 | 通过 | 生命周期和项目绑定 409 测试 |
| 7 | 校验并主动启用后才可绑定 | 通过 | 三类定义、节点、流转、初始状态启用校验 |
| 8 | 关联项目时不能停用 | 通过 | 停用保护返回 409 和项目数量 |
| 9 | 项目切换后才可停用原方案 | 通过 | 解绑/切换后停用成功测试 |
| 10 | 业务对象通过 `current_state_id` 展示 `status_name` | 通过 | 模型、API、工作台和前端显示测试 |
| 11 | 修改中文名称不改变状态关联 | 通过 | 重命名后状态 ID 和流转 ID 保持不变 |
| 12 | 流转边使用状态节点 ID | 通过 | 图读写、动作发现、执行和审计均校验状态 ID |
| 13 | 保存流程图不改变已有状态 ID | 通过 | 两次增量保存 ID 保持断言 |
| 14 | 被引用状态不能物理删除 | 通过 | 省略引用节点时转为停用的回归测试 |
| 15 | 每张定义只有一个有效初始状态 | 通过 | 单一 `initial_state_id` 和归属/启用校验 |
| 16 | 初始状态不因处理人而改变 | 通过 | 有负责人和无负责人创建结果的状态 ID 相同 |

## 4. 数据库实施结果

### 4.1 已完成

- `20260716_001_workflow_state_identity.py`：增加并回填定义、状态、流转、业务对象和操作历史的 ID 引用。
- `20260716_002_remove_core_status_columns.py`：校验引用完整性后，删除 `requirements/tasks/bugs.status`，并将定义 ID、当前状态 ID 收紧为非空。
- `audit_workflow_state_migration.py`：只读检查空引用、悬空引用、跨定义状态、非法流转端点、非法初始状态和遗留核心状态列。
- 该阶段已在隔离 MySQL 库实际执行 `002 -> 001 -> 002` 往返，当时的最终 revision 为 `20260716_002 (head)`；最新 head 见第 4.2 节。

### 4.2 2026-07-17 状态 ID 化收尾

- `20260717_001_project_iteration_state_identity.py`：为项目、迭代增加并回填 `workflow_definition_id/current_state_id`。
- `20260717_002_remove_workflow_state_strings.py`：在完整性审计通过后，将项目、迭代和流转端点 ID 收紧为非空，删除 `projects.status`、`iterations.status`、`workflow_states.status_key`、`workflow_transitions.from_status/to_status`，并删除 `handler_transition_rules` 表。
- 五类业务对象、工作流定义、状态节点和流转边的运行模型共有 15 个工作流身份外键，所有目标 ID 均有查询索引；状态历史日志另有 3 个快照关联外键。
- 项目、迭代 API 与页面通过 `workflow_definition_id/current_state_id/status_name/state_category` 读写和展示状态，不再返回或判断状态编码。
- `Program.status` 和 `workflow_transitions.action_key` 按确认范围保留。
- 处理人配置以 `workflow_transitions.handler_rule` 为唯一来源。隔离库往返验证中，102 条原独立处理人规则降级可重建、再次升级后数量、总字节数和内容指纹均保持不变。

## 5. 验证结果

初次验证日期：2026-07-16。2026-07-17 又在独立 MySQL 数据库 `intellective_bio_sdlc_workflow_state_model_test` 完成状态 ID 化收尾技术复核；浏览器行保留 2026-07-16 的历史验收结果，并非本轮重跑。

| 验证项 | 结果 |
|---|---|
| 后端全量 `python -m pytest -q` | 264 passed，0 failed；1007 条第三方弃用告警 |
| 数据迁移审计 | `ok: true`，`issues: []` |
| Alembic 当前版本 | `20260717_002 (head)` |
| Alembic 收尾迁移往返 | `20260717_002 -> 20260717_001 -> 20260717_002` 成功 |
| 处理人规则往返 | 102 条；前后总字节数 14121；SHA-256 均为 `911f7e611da9a4c697629dcb215ca21c22ca313f648554d417e066ff3caa3e00` |
| 前端全量 `npm test` | 全部通过，终末 TAP 汇总 9 passed、0 failed |
| 前端生产构建 `npm run build` | 成功，1745 个模块，11.35 秒 |
| 浏览器桌面验收（2026-07-16） | 空白/模板模式、来源分组、系统复制、已有方案复制、启用操作和设计器加载均通过 |
| 浏览器移动验收（2026-07-16） | 390×844 无横向溢出，主要操作控件均在容器边界内 |
| `git diff --check` | 无空白错误 |

非阻断告警：

- 后端测试仍有 `python-jose` 使用 `datetime.utcnow()` 的第三方弃用告警。
- 前端构建仍有 Rollup PURE 注释和单块大于 500 kB 的性能告警。

这些告警未影响本 PRD 功能正确性，但建议在后续依赖升级和前端拆包任务中处理。

## 6. 未实现功能说明

PRD 第 9 章的 9 项内容仍是待后续产品确认项，不计为本次验收缺陷。其中前 3 项为保证当前功能可运行，代码已经存在以下临时规则，但这些规则仍需业务验收，不能视为已确认的最终产品结论：

1. 已有方案进入模板来源列表时不按草稿、已启用、已停用过滤，但必须同时存在需求、任务、Bug 三个启用的工作流定义；缺少核心定义的历史数据会被排除。
2. 方案名称当前不允许重复，创建或改名冲突返回 HTTP 409。
3. 启用校验当前要求需求、任务、Bug 各有且仅有一个启用定义；每个定义有一个属于自身的启用初始状态、至少一条启用流转，且所有启用流转端点均为该定义内的启用状态。

其余 6 项未实现：已启用方案编辑限制、方案删除、停用恢复、终态新规则、节点处理模式，以及工作台展示/超时计算的节点级独立配置。未实现原因是这些行为会改变运行中业务数据和流程治理边界，PRD 尚未给出可执行规则，不能代替产品决策。

FR-1 至 FR-13、16 条验收标准及 2026-07-17 状态 ID 化收尾范围没有已知未实现项。

## 7. 交付提交

| 提交 | 内容 |
|---|---|
| `a8a3e9b` | 状态身份字段和回填迁移 |
| `fbcf45d` | ID 图保存和状态增量更新 |
| `035bb5c` | 方案生命周期 |
| `165c983` | 统一模板来源和独立复制 |
| `ce3fb17` | ID 运行时和初始状态创建 |
| `468803e` | 移除状态字符串运行时判断 |
| `6ead11a` | 方案创建与生命周期前端 |
| `a6107b0` | ID 设计器和中文状态展示 |
| `3b59210` | 删除核心旧状态列、仓库守卫和审计脚本 |
| `c7f0cbc` | 核心目标状态 ID 路由 |
| `0f3d74d` | 增加项目、迭代工作流定义和当前状态 ID，执行旧数据回填 |
| `1096466` | 系统模板改为通过状态 ID 持久化 |
| `3bd42b8` | 项目、迭代工作流运行时切换为状态 ID |
| `e5695f5` | 流转内 `handler_rule` 成为处理人规则唯一来源 |
| `4b1e661` | 项目、迭代 API 和页面展示中文状态名及节点分类 |
| `af97204` | 删除旧状态字符串身份、旧处理人规则表并加入最终审计 |
