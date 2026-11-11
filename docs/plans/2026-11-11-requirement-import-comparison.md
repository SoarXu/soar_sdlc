# Requirement import comparison and export implementation plan

**Goal:** 在项目详情中导出需求，再通过 Excel 预览字段差异、确认 AD 提出人并批量更新。

**Architecture:** 扩展现有需求导入接口与模板兼容，不新增数据库字段。预览/提交共享行解析和差异计算，提交重新校验 AD 及预览快照。前端独立导入组件逐行展开差异、选择提出人或跳过。导出全部当前项目有效需求（不局限分页），追加需求ID以支持标题修改，旧表无ID时保持项目+标题匹配。

**Tech stack:** FastAPI / SQLAlchemy / openpyxl / Vue 3 / Element Plus。

## Task 1: 行预览及更新
- 修改 `backend/app/services/requirement_import_service.py`、`backend/app/views/requirement_view.py`。
- 先增加接口回归测试：差异、无变化跳过、ID定位、空提出人保留、状态和处理人保留。
- 预览返回每行原值/新值、动作、AD匹配结果、快照；确认前不得写入。
- 同项目同标题多条时拒绝自动定位；禁止跨项目ID；同一文件重复更新同一需求需报错。

## Task 2: AD 及确认
- 使用当前已测试启用的LDAP配置查询AD，分页遍历匹配候选；账号/工号优先精确匹配，其次唯一姓名。
- 未匹配/重名/目录不可用标待确认；非空提出人未经确认不得提交。
- 支持按行覆盖AD external_id和跳过；提交重新查AD，校验快照冲突，全部校验完成才写入。
- 以接口测试覆盖重名选择、伪造选择、目录失败、快照冲突、不出现部分落库。

## Task 3: 导出
- 在 `backend/app/controllers/requirement_controller.py` 增加有项目查看权限校验的导出接口。
- 使用现有模板列、数据验证，追加需求ID；Excel文本禁止被当作公式，富文本原样保留以支持往返更新。
- 回归测试验证项目隔离、全部需求导出、ID往返修改标题和无变化导入。

## Task 4: UI
- 新建 `frontend/src/components/RequirementImportDialog.vue`；替换项目详情原导入弹窗及旧逻辑。
- 增加导出按钮，Excel预检后始终等待人工确认；变更策略/提出人/跳过后必须重新预检。
- 表格展开显示旧值/新值，AD下拉值使用唯一ID，支持姓名、账号、工号检索和部门区分。
- 在 `frontend/src/api/requirements.js` 扩展上传参数及导出。
- 增加前端行为测试，验证预检失效、未解决阻断、提交失败不关闭和导出下载。

## Validation and delivery
- 运行需求导入接口测试、相关LDAP及项目权限测试、前端行为测试与构建；本地HTTP检查。
- 仅保留本地修改，未经用户确认不提交/推送，不更改已有部署包。

## 验证记录
- 需求导入/导出接口与对比回归：43 项通过；LDAP 相关：43 项通过。
- 相关前端行为测试通过；生产构建通过（存在原有大包提示）。
- 实际页面导出当前项目 3 条需求，在内存文件中修改标题和优先级后预检，显示 1 条更新、2 条无变化，无浏览器异常；未提交到业务数据库。
- 独立复核发现并修复新标题并发导入冲突、Excel 超长字段静默截断；增加回归覆盖。超限导出明确提示需求ID和字段。
- 全量前端测试被已有缺失 `deployment/docker-compose.yml` 阻断；项目权限测试收集被已有缺失 `UserRole` 导入阻断。本次不修改这些既有问题。
- 不新增数据库字段或迁移；不重建部署包。
