# 工作项提交追溯与代码评审设计

## 目标

让需求、任务和缺陷详情页展示所有关联提交，并从同一处完成代码差异查看、Git 平台跳转和工作项评审。提交说明中的工作项编号自动建立关联；只有明确提请评审的 Git 事件才驱动工作流从处理中进入待评审。

## 设计原则

- 一个提交只保存一份。`DevopsCommit` 是提交事实，`DevopsCommitLink` 是提交与工作项的多对多关联，不复制 Diff 或评审结论。
- 普通提交是研发证据，不等同于开发完成。仅关联 `REQ-<id>`、`TASK-<id>`、`BUG-<id>` 时，不改变工作项状态。
- 明确的评审信号才创建评审轮次并流转状态。第一期支持提交说明中的 `#review` 或 `Review-Ready: true`；后续 Gitea、GitLab、GitHub Pull Request 的 Ready for review 事件复用同一逻辑。
- Diff 使用本地快照优先。入库载荷带 Diff 时立即保存；缺少 Diff 时按需从已配置 Git 平台补拉并缓存。平台不可用不丢失提交关联。
- 评审范围必须冻结。评审结论绑定一轮提交快照，待评审期间的新关联提交使当前结论失效并要求重新评审。

## 现状与复用

系统已有：

- `DevopsCommit`：保存 SHA、仓库、平台 URL、Diff、评审字段。
- `DevopsCommitLink`：以 `(commit_id, object_type, object_id)` 唯一约束关联需求、任务、缺陷。
- `WorkItemReviewRound`：保存工作项评审轮次、评审人和结论。
- `CommitRecordsPanel` 与 `CommitDiffViewer`：已在三类工作项详情页挂载，可展示本地提交和 Diff。

现有不足：详情页提交面板缺少外链、Diff 获取状态和工作项评审入口；Gitea/GitHub 未纳入统一的提交/Diff 获取契约；评审轮次无法冻结多条 Commit 的范围。

## 数据模型

### 提交

扩展 `devops_commits`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `diff_status` | string | `available`、`pending`、`fetching`、`failed`、`empty` |
| `diff_fetched_at` | datetime nullable | 最近一次成功获取 Diff 的时间 |
| `diff_error` | text nullable | 最近一次获取失败的用户可见原因 |

继续使用已有 `web_url` 作为外部提交页面地址。只信任平台载荷或平台 API 返回的地址；缺失时不自行拼接 URL。

### 评审轮次提交快照

新增 `work_item_review_commits`：

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `review_round_id` | `WorkItemReviewRound.id` |
| `commit_id` | `DevopsCommit.id` |
| `sort_order` | 本轮提交顺序 |
| `create_time` | 快照生成时间 |

对 `(review_round_id, commit_id)` 设置唯一约束。该表只保存引用，不复制提交数据；已关闭轮次的快照不可因后续提交而修改。

## 事件与状态规则

提交说明推荐格式：

```text
实现缺陷校验
Refs: BUG-45 TASK-30
Review-Ready: true
```

兼容现有 `REQ-12`、`TASK-30`、`BUG-8` 识别方式。

| 事件 | 提交关联 | 评审轮次 | 工作项状态 |
| --- | --- | --- | --- |
| 普通关联 Commit | 自动建立 | 不创建 | 保持处理中 |
| `#review` / `Review-Ready: true` | 自动建立 | 创建并冻结当前关联 Commit | 中处理到待评审 |
| 待评审期间新增关联 Commit | 自动建立 | 现有轮次标记需重新评审；创建下一轮快照 | 返回处理中 |
| 评审通过 | 不变 | 当前轮次关闭并记录结论 | 执行待评审后的既有流转 |
| 评审驳回 | 不变 | 当前轮次关闭并记录意见 | 返回处理中 |

第一期由后端提交事件处理器调用既有工作流运行时服务执行状态流转，不允许前端伪造自动流转。Pull Request Ready 事件作为第二期输入，进入相同的领域事件处理器。

## 界面设计

### 工作项详情页

需求、任务、缺陷详情页复用一个提交面板，展示：

- SHA、提交标题、分支、提交人、提交时间。
- Diff 状态和当前评审轮次状态。
- 点击 SHA 打开本地 Diff/评审抽屉。
- 外链图标在新标签页打开 `web_url`。
- 待评审状态下显示“代码评审”命令，仅评审人、开发主管和系统管理员可用。

### Diff 与评审抽屉

- 默认展示评审轮次的汇总 Diff，并允许切换到单个 Commit。
- 本地无 Diff 时显示加载状态，调用服务端补拉并缓存；失败时展示原因和平台外链。
- 无关联 Commit 时，不显示可通过的评审界面，提示开发先提交含工作项编号的代码。
- 评审人可填写整体意见和行级意见，执行通过或驳回。
- 检测到评审创建后新增 Commit 时，禁用旧轮次的通过按钮，提示重新评审。

### DevOps 页面

保留 DevOps 作为跨工作项的提交与待办总览。详情页和 DevOps 页面读取相同提交、评审轮次和结论；任何一处完成评审后另一处刷新为同一状态。

## 服务接口

保留：

- `GET /devops/commits?object_type=&object_id=`
- `GET /devops/commits/{commit_id}`
- `POST /devops/work-item-reviews/{review_round_id}/decision`

扩展或新增：

| 接口 | 用途 |
| --- | --- |
| `GET /devops/work-item-reviews/{id}/commits` | 返回冻结的 Commit 列表、汇总 Diff 与评审上下文 |
| `POST /devops/commits/{id}/fetch-diff` | 使用仓库所属平台连接拉取并缓存 Diff |
| 提交 Webhook 统一入口/适配层 | 将 Gitea、GitLab、GitHub 提交规范化为同一提交关联事件 |

提交查询响应增加 `web_url`、Diff 状态、错误原因和评审摘要。外部 Token 仅由后端解密使用，不出现在任何响应中。

## 权限与失败处理

- 所有能查看工作项的用户可查看关联提交、已缓存 Diff 和平台外链。
- 当前评审人、开发主管和系统管理员可执行评审结论；转交仍在 DevOps 工作台完成。
- 平台连接缺失、失效或无权限时，记录 `diff_error`，保留提交关联和外链。
- 外部 Diff 为空时记录 `empty`，评审界面明确提示“该提交无可展示代码差异”。
- 工作项不存在或已删除时，不建立新的 Commit 关联。

## 验收标准

1. 普通带工作项编号的 Commit 会出现在对应需求、任务、缺陷详情页，但不改变工作项状态。
2. 带评审标记的 Commit 会创建提交快照并自动流转到待评审。
3. 三类详情页均可打开本地 Diff 和 Git 平台外链。
4. 本地缺少 Diff 时可补拉、缓存、显示失败原因。
5. 无关联 Commit 时不能通过评审。
6. 待评审后新增 Commit 会使旧轮次失效并要求重新评审。
7. 通过和驳回只允许授权角色操作，并正确驱动既有工作流。
