# 工作项删除一致性验证计划

## 验证目标

验证已完成任务与非终态任务的删除入口一致，且删除存在未删除关联任务的需求被原子阻断。

## 自动化验证

```powershell
cd backend
pytest tests/test_requirement_delete_linked_tasks_api.py tests/test_task_hierarchy_api.py tests/test_requirement_task_api.py -v
cd ../frontend
node src/views/workItemDeleteConsistency.test.mjs
npm test
npm run build
git diff --check
```

通过标准：任务树中任何未删除节点均阻断需求删除；阻断响应为 `409`、含 `REQUIREMENT_HAS_LINKED_TASKS` 和精确数量；失败后需求、任务 `requirement_id` 与审计行不变；已删除任务不阻断；三类任务页面入口都不因已完成状态隐藏删除。

## 页面验收

1. 以有删除权限用户打开已完成任务的全局列表、项目任务页与任务详情，确认均可见“删除”。
2. 删除已完成任务，确认成功并刷新或返回列表。
3. 打开有关联根任务及子任务的需求，确认删除得到可理解提示，需求和任务仍可查看且关联未变。
4. 删除或软删除全部关联任务后，确认需求可按原有规则删除。
5. 使用无删除权限用户确认入口不可见，直接 API 仍被拒绝。
