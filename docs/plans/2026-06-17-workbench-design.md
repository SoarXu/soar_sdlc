# Workbench Design

## Goal

工作台用于让用户按迭代和负责人查看当前阶段需要完成的需求、任务、测试用例和 Bug，并能直接完成状态流转或将卡片拖拽到其他迭代。

## Scope

- 工作台作为首页 `/`，替换现有只展示统计数字的 Dashboard。
- 每个迭代是一个板块，板块内展示需求、任务、测试用例、Bug 四类工作项。
- 支持负责人筛选和对象类型筛选。默认展示全部负责人，后续数据隔离启用后默认切换为当前用户。
- 卡片展示标题、项目、负责人、状态、优先级或执行结果、截止日期等关键字段。
- 卡片提供生命周期操作，复用现有业务规则和后端接口。
- 支持跨迭代拖拽，拖拽后必须落库。

## Data Rules

- 需求：以 `requirements.iteration_id` 作为迭代归属。
- 任务：以 `tasks.iteration_id` 作为直接迭代归属；若任务关联了需求，也要随需求在迭代详情中自然展示。
- 测试用例：新增 `test_cases.iteration_id` 字段，支持直接归属迭代；同时保留通过需求归属迭代的既有展示规则。
- Bug：以 `bugs.iteration_id` 作为解决迭代或工作台归属。
- 未归属迭代的对象暂不进入迭代板块，后续可增加“未规划”板块。

## Status Operations

- 需求：激活、关闭。
- 任务：激活、关闭。
- 测试用例：执行；失败或阻塞后可提 Bug。
- Bug：确认、解决、激活、挂起、关闭。
- 工作台不绕过业务规则，全部调用已有生命周期接口。

## Drag And Drop

- 使用 `vue-draggable-plus`，基于 SortableJS，支持 Vue 3、多列表拖拽、动画和触摸设备。
- 拖拽成功后调用后端统一迁移接口。
- 后端按对象类型更新对应的 `iteration_id`。
- 如果后端返回失败，前端回滚工作台数据并提示原因。
- 需求拖拽到新迭代后，需求关联的任务、用例仍保留自身字段；迭代详情仍按需求关系同步展示。

## Backend Shape

- `GET /api/v1/dashboard/workbench`
  - 返回迭代板块、负责人列表、每个板块下四类工作项和统计。
- `POST /api/v1/dashboard/workbench/move`
  - 入参：`object_type`、`object_id`、`target_iteration_id`。
  - 支持：`requirement`、`task`、`test_case`、`bug`。
  - 返回更新后的工作项摘要。

## Frontend Shape

- `DashboardView.vue` 改为工作台页面。
- 新增 `frontend/src/api/dashboard.js` 方法。
- 卡片使用紧凑看板样式，支持横向滚动和响应式折叠。
- 状态操作弹窗尽量复用现有交互文本和原因选项。

## Validation

- 后端测试覆盖：
  - 工作台按迭代聚合四类对象。
  - 测试用例支持 `iteration_id`。
  - 拖拽迁移接口更新对应对象的 `iteration_id`。
- 前端构建必须通过。
- sub-agent 审查目标覆盖，未达 90 分继续补齐。
