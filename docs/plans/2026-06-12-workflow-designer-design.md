# 工作流配置面板设计

## 背景

平台已有 `workflow_rules` 表和工作流配置入口，但还没有可操作页面和接口。现有项目、需求、任务、用例、Bug 已经存在多处状态联动逻辑。为了避免一次性引入过重的流程引擎，第一版工作流配置先聚焦“可视化配置、规则落库、模板沉淀”，后续再逐步让业务动作读取配置执行。

## 目标

- 工作流配置页面支持左侧组件库、中间工作流画布、右侧节点属性配置。
- 节点可以作为组件添加到工作流，并设置上下级触发关系。
- 支持以“项目关闭触发项目中未关闭需求状态变更，并选择状态变更结果”为示例模板。
- 工作流配置保存到 `workflow_rules.condition_json` 和 `workflow_rules.action_json`。
- 后端提供工作流规则 CRUD 与默认模板接口。

## 节点模型

节点分为三类：

1. 触发节点
   - 项目状态变更
   - 项目集状态变更
   - 迭代状态变更
   - 需求状态变更
   - 任务状态变更
   - Bug 状态变更
   - 测试用例执行结果
   - 字段变更

2. 条件节点
   - 当前状态匹配
   - 子对象存在未关闭数据
   - 字段为空/不为空
   - 用户角色匹配
   - 对象范围匹配
   - 结果匹配，例如用例失败/阻塞

3. 动作节点
   - 修改当前对象状态
   - 批量修改子对象状态
   - 设置负责人
   - 创建 Bug
   - 创建通知
   - 阻断操作并提示
   - 写入操作历史
   - 同步字段

## 画布数据结构

`condition_json` 保存画布结构：

```json
{
  "designer_version": 1,
  "nodes": [
    {
      "id": "node-1",
      "component_key": "project_status_changed",
      "category": "trigger",
      "label": "项目状态变更",
      "x": 80,
      "y": 80,
      "config": {
        "from_status": "*",
        "to_status": "closed"
      }
    }
  ],
  "edges": [
    {
      "id": "edge-1",
      "source": "node-1",
      "target": "node-2"
    }
  ]
}
```

`action_json` 保存可执行摘要：

```json
{
  "trigger": {
    "target_object": "project",
    "trigger_action": "status_changed",
    "to_status": "closed"
  },
  "steps": [
    {
      "type": "condition",
      "component_key": "child_unclosed_exists",
      "config": {
        "child_object": "requirement",
        "status_not_in": ["closed"]
      }
    },
    {
      "type": "action",
      "component_key": "batch_change_child_status",
      "config": {
        "child_object": "requirement",
        "target_status": "closed",
        "reason": "不做"
      }
    }
  ]
}
```

## 默认模板

第一版内置模板：

- 项目关闭 -> 关闭未关闭需求 -> 关闭关联任务
- 需求激活 -> 关联任务进行中
- 用例失败/阻塞 -> 允许提 Bug
- Bug 修复完成 -> 通知测试验证
- 迭代完成前 -> 校验需求全部关闭

## 前端交互

- 左侧组件库按“触发 / 条件 / 动作”分组。
- 用户点击或拖拽组件到画布。
- 画布节点以纵向流程展示，节点可拖动调整位置。
- 选中节点后右侧显示属性配置表单。
- 点击节点上的“连接到”选择下级节点，形成上下级触发关系。
- 保存时生成 `condition_json` 和 `action_json` 并调用后端接口。

## 后端接口

- `GET /api/v1/workflow-rules`
- `POST /api/v1/workflow-rules`
- `PATCH /api/v1/workflow-rules/{id}`
- `DELETE /api/v1/workflow-rules/{id}`
- `GET /api/v1/workflow-rules/components`
- `GET /api/v1/workflow-rules/templates`

## 非目标

- 第一版不替换现有项目关闭、需求关闭等业务逻辑。
- 第一版不实现完整 BPMN、分支网关、循环、并发任务。
- 第一版不做权限细粒度控制，仅提供页面和数据结构基础。
