# 缺陷工作流确认动作去重验证计划

## 验证目标

确认 N-004 的历史重复“确认缺陷类型”动作被安全规范化，且不会放宽工作流图保存校验或影响正常缺陷流转。

## 自动化验证

| 编号 | 场景 | 步骤 | 预期结果 |
| --- | --- | --- | --- |
| V-01 | 重复动作修复 | 构造系统管理缺陷图，在 `active_work` 创建两条启用的 `confirm_bug_type`。 | 协调后只保留一条启用动作，ID 最小者为规范记录，额外记录停用。 |
| V-02 | 停用原因 | 检查被去重的额外记录。 | `auto_disabled_by_state=False`，说明它不是状态停用联动产生的动作。 |
| V-03 | 幂等性 | 对 V-01 的图连续协调两次。 | 第二次无数据变更、定义版本不增加、不会新增流转。 |
| V-04 | 模板配置 | 读取保留动作的表单、路由、处理人和 UI 配置。 | 与 `_bug_confirmation_transition()` 一致，仍可在修复中执行确认缺陷类型。 |
| V-05 | 数据迁移 | 检查 Alembic 链并执行升级。 | 新迁移位于 `20260822_006` 之后，唯一 head 为新 revision，并调用同一协调函数。 |
| V-06 | 流程图保存 | 读取已规范化流程图后原样保存。 | 返回成功，不再出现“重复已启用流转名称来源状态”。 |

## 回归与验收

- 后端测试必须串行执行，避免共享 MySQL 测试夹具并发清理数据：`test_bug_workflow_action_alignment_migration.py`、`test_workflow_definition_api.py`、`test_default_workflow_templates_api.py`、`test_bug_workflow_api.py`。
- 执行 `alembic upgrade head`、`alembic current`、`alembic heads`、`python -m compileall -q app` 和 `git diff --check`。
- 手工验收：刷新后台管理的缺陷流程图，确认“确认缺陷类型”只保留一条可用流转，点击“保存流程图”成功；在修复中 Bug 详情确认仍显示并能执行该动作。

## 验证结果

- `pytest tests/test_bug_workflow_action_alignment_migration.py -q`：9 项通过，覆盖重复动作收敛、旧动作迁移不重复插入、保存服务成功和迁移链。
- `pytest tests/test_workflow_definition_api.py -q`：48 项通过；`pytest tests/test_default_workflow_templates_api.py -q`：13 项通过；`pytest tests/test_bug_workflow_api.py -q`：15 项通过。由于共享 MySQL 夹具跨文件并行/组合执行会相互创建和清理方案，组合运行出现的 `StaleDataError` 已通过按文件单独串行复跑排除。
- 数据库已执行 `alembic upgrade head`，`alembic heads` 与 `alembic current` 均输出 `20260824_001 (head)`。三个受影响定义各保留一条启用确认动作，三条副本停用且未标记为状态联动停用。
- 使用本地后端实际接口读取定义 `547`，按前端 `serializeWorkflowTransition` 的规则去除历史 UI 兼容字段后保存，`GET` 与 `PUT` 均返回 `200`。
- `python -m compileall -q app` 与 `git diff --check` 通过。
