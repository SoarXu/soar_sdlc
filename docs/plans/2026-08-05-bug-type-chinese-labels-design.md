# Bug 类型中文展示设计

## 目标

在项目详情、迭代详情的 Bug 列表和 Bug 详情基础信息区展示 Bug 类型字典的中文名称，而非类型代码。

## 范围

- 修改 `ProjectDetailView.vue` 的 Bug 类型表格单元格。
- 修改 `IterationDetailView.vue` 的 Bug 类型表格单元格。
- 在 `BugDetailView.vue` 的基础信息描述区新增“Bug 类型”。
- 不修改 Bug 类型接口、后端返回、工作流路由、编辑表单或类型字典内容。

## 方案

三个页面均已使用 `useBugTypes()` 加载类型字典。将其返回值中的 `bugTypeLabel` 与既有的 `bugTypeOptions` 一并解构，在两个列表调用 `bugTypeLabel(row.bug_type)`，在详情描述项调用 `bugTypeLabel(bug.bug_type)`。

`bugTypeLabel()` 在字典命中时返回 `display_name`，未命中时回退原始代码或 `-`。因此自定义类型可显示中文，历史或失效类型仍保持可识别。

## 验证

新增前端源契约测试，确认三个页面均解构并调用 `bugTypeLabel`，且 Bug 详情包含“Bug 类型”描述项。执行该测试、前端全量测试、生产构建和差异检查。
