# 业务组件角色与配置入口实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让业务组件成员使用后台角色，并将业务组件纳入项目配置页的子页签。

**Architecture:** 后端以后台角色 `role_key` 校验组件成员及路由候选人；前端复用现有组件管理逻辑，以项目配置页的内部路由状态承载两个子页签，并兼容旧地址。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Vue Router, Element Plus, pytest, Node.js.

---

### Task 1: N-017 后端角色校验

**Files:**
- Modify: `backend/app/services/business_component_service.py`
- Test: `backend/tests/test_business_components_api.py`

1. 为“项目成员但未分配所选后台角色”编写失败接口测试。
2. 运行该测试，确认当前内部职责模型未满足要求。
3. 校验角色启用状态、用户角色分配和项目成员资格；路由仅选中拥有组件角色的成员。
4. 运行组件 API 测试，确认通过。

### Task 2: N-017 前端角色选择

**Files:**
- Modify: `frontend/src/views/ProjectComponentsView.vue`
- Test: `frontend/src/views/projectComponentsView.test.mjs`

1. 为后台角色 API 和旧内部职责移除编写失败源码契约测试。
2. 加载后台启用角色，以角色名称渲染选择器并提交 `role_key`。
3. 运行前端契约测试，确认通过。

### Task 3: N-018 配置页迁移

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/ProjectComponentsView.vue`
- Modify: `frontend/src/router/index.js`
- Test: `frontend/src/views/projectConfigurationTabs.test.mjs`

1. 为配置页的两个子页签、默认页和旧地址重定向编写失败测试。
2. 将组件管理内容复用到项目配置的“业务组件”子页签，删除标题独立入口。
3. 令旧组件地址重定向到 `tab=settings&settingsTab=components`。
4. 运行子页签测试，确认通过。

### Task 4: 回归与交付

1. 运行后端组件测试和全部前端测试、构建。
2. 更新 N-017、N-018 为已解决并写入验证结果。
3. 逐项提交，合并或直接提交至 `main`，执行 `git diff --check` 后推送 `origin/main`。
