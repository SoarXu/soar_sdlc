# 工作流清理说明

## 目标

当前工作流配置以可视化工作流方案为准。历史的处理人流转矩阵和旧 `workflow_rules` 规则容易和可视化工作流形成双配置来源，本次清理先收敛公开入口，保留必要的运行时兼容。

## 已清理

- 下线公开的 `/api/v1/handler-transition-matrix` 接口。
- 删除前端 `handlerTransitionMatrix` API 客户端。
- `handler_transition_rules` 不再接受 `rule_type=matrix` 的新规则。
- 处理人自动分配改为读取可视化工作流同步出的 `rule_type=advanced` 规则。
- 项目详情页不再加载旧 `/workflow-rules` 数据。

## 暂时保留

- `handler_transition_rules` 表继续保留，作为可视化工作流流转规则的运行时表。
- `workflow_rules` 和 `workflow_engine` 暂时保留，因为项目关闭、需求关闭联动仍有调用。
- `/api/v1/workflow-rules` 已标记为 deprecated，后续迁移项目/需求关闭联动后再删除。

## 后续清理顺序

1. 将项目关闭、需求关闭的联动规则迁移到 `workflow_definitions` / `workflow_transitions`。
2. 删除旧 `workflow_rules` 的前后端 API、模型和执行引擎。
3. 迁移或归档旧的矩阵 PRD，避免作为新开发依据。
