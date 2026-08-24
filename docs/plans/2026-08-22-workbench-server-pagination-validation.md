# 工作台服务端分页验证计划

## 目标

验证活动迭代工作项列表在数据量增长时仍只传输当前页数据，同时保持权限边界、筛选选项、旧聚合接口和工作流动作入口正确。

## 自动化验证

```powershell
cd backend
pytest tests/test_workbench_pagination_api.py tests/test_requirement_delete_linked_tasks_api.py -v
python -m compileall -q app
cd ../frontend
node src/utils/workbenchViewModel.test.mjs
node src/views/workItemDeleteConsistency.test.mjs
npm test
npm run build
git diff --check
```

通过标准：

- 120 条可见工作项、每页 20 条时，响应仅含 20 条、`total=120`、相邻页没有重复。
- 项目、迭代、类型、状态、优先级、处理人和关键字筛选由接口执行；筛选选项不随页码或当前筛选收缩。
- 普通成员不能看到未参与项目的数据或筛选项；旧 `/dashboard/workbench` 响应保持可用。
- 前端请求包含页码及所有筛选条件；流转批量请求只取响应的 `items`。
- 验证过程中的 pytest 必须使用单一串行进程，避免共享 MySQL 夹具相互清理临时数据。

## 页面验收

1. 为一个当前用户可见的进行中迭代准备超过 100 条需求、任务和 Bug。
2. 打开工作台，确认首屏仅加载当前页，切换页码、页大小和任一筛选条件后列表与总数同步更新。
3. 在第二页检查工作流按钮请求的对象数量不超过当前页大小。
4. 使用普通项目成员登录，确认未参与项目不在列表和筛选项中。
5. 打开仍使用旧聚合接口的工作台分区，确认其数据和操作不受影响。
