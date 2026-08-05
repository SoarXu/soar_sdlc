# 迭代动作直显设计

## 目标

在迭代详情页、迭代列表和项目详情页的迭代操作列中，将当前可执行的迭代生命周期动作直接显示，不再收进“更多”菜单。

## 范围

- 仅影响对象类型为 `iteration` 的运行时工作流动作。
- 覆盖“开始”“完成”“取消”等当前状态可执行的迭代生命周期动作。
- 不修改工作流定义、动作权限、确认表单、阻断校验或状态流转逻辑。
- 不改变项目、需求、任务或 Bug 的动作分组行为。

## 方案

在 `frontend/src/utils/workflowRuntimeActions.js` 的 `splitListActions()` 中，将迭代对象的全部可见动作归入 `primaryActions`，并使 `moreActions` 为空。三个目标页面均已通过 `WorkflowActionButtons` 传入 `object-type="iteration"`，因此无需在页面中增加重复的展示开关。

该规则只改变前端展示分组；按钮仍由同一组件发起既有工作流请求，现有的权限、日期表单、完成/取消阻断提示和刷新行为保持不变。

## 验证

在 `workflowRuntimeActions.test.mjs` 中先增加失败断言：包含“开始”“完成”“取消”的迭代动作输入应按排序全部出现在 `primaryActions`，`moreActions` 为空。验证项目和其他对象的既有分组断言仍然通过，再运行前端全量测试、构建和差异检查。
