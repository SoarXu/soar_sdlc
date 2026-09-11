# LDAP/AD Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 提供可配置的 AD/LDAP 员工查询、人工选择同步、现有用户绑定、AD 登录认证及每周资料更新能力。

**Architecture:** 后端以独立 LDAP 配置、查询和同步服务封装 `ldap3`，只向前端返回白名单属性；用户表保存认证来源和稳定的目录标识，不保存 AD 用户密码。前端在 LDAP 配置页采用左右布局完成配置与域用户选择，登录入口保持不变，由后端按用户认证来源分流。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、ldap3、cryptography/Fernet、Vue 3、Element Plus、Node test、pytest。

---

### Task 1: 扩展用户模型并迁移现有用户

**Files:**
- Create: `backend/alembic/versions/20260910_001_add_ldap_user_fields.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/views/user_view.py`
- Modify: `backend/app/services/user_service.py`
- Modify: `frontend/src/views/RolesView.vue`
- Test: `backend/tests/test_user_api.py`
- Test: `frontend/src/views/userSystemAdminOnly.test.mjs`

**Steps:**

1. 先新增失败测试：现有用户读取时 `auth_source == "local"`；创建/编辑用户可保存唯一的 `employee_no`；LDAP 用户响应不暴露密码字段。
2. 运行 `cd backend; pytest tests/test_user_api.py -q`，确认新断言失败。
3. 在 `users` 表新增 `employee_no`、`auth_source`、`ldap_external_id`、`ldap_dn`、`ldap_last_synced_at`；迁移将现有行设为 `local`。为非空工号和 LDAP 唯一标识建立唯一索引。
4. 扩展 `UserRead`/`UserCreate`，增加普通用户编辑接口 `PATCH /users/{id}`；工号允许为空，空字符串统一转为 `NULL`。
5. 在用户列表账号后增加工号列；新增/编辑表单增加工号；LDAP 用户隐藏重置密码操作并显示“AD 用户”来源。
6. 分别运行后端目标测试和 `cd frontend; npm test -- userSystemAdminOnly`，确认通过。
7. 交付检查点：仅在主上明确确认后提交本任务文件。

### Task 2: 建立 LDAP 配置与安全存储

**Files:**
- Create: `backend/app/models/ldap_integration.py`
- Create: `backend/app/views/ldap_view.py`
- Create: `backend/app/services/ldap_config_service.py`
- Create: `backend/app/controllers/ldap_controller.py`
- Create: `backend/alembic/versions/20260910_002_add_ldap_integration.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/security.py`
- Test: `backend/tests/test_ldap_config_api.py`

**Steps:**

1. 写失败测试覆盖系统管理员权限、默认 AD 映射、创建时密码必填、更新时空密码保留、GET 永不返回密码或密文。
2. 运行 `cd backend; pytest tests/test_ldap_config_api.py -q`，确认失败。
3. 创建单实例 LDAP 配置模型，包含启用状态、协议、主机、端口、超时、Base DN、用户 Base DN、筛选器、排除禁用项和七个属性映射字段。
4. 将通用密钥配置为 `INTEGRATION_ENCRYPTION_KEY`；保留现有 Git 密钥兼容读取路径，使用 Fernet 加密绑定密码。
5. 实现 `GET /admin/ldap` 和 `PUT /admin/ldap`，只允许系统管理员访问；启用前检查最近一次连接测试成功且配置未在测试后改变。
6. 运行目标测试，确认权限、验证和脱敏全部通过。
7. 交付检查点：仅在主上明确确认后提交本任务文件。

### Task 3: 实现 LDAP 连接、测试和目录查询

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`
- Create: `backend/app/services/ldap_client.py`
- Modify: `backend/app/services/ldap_config_service.py`
- Modify: `backend/app/controllers/ldap_controller.py`
- Test: `backend/tests/test_ldap_client.py`
- Test: `backend/tests/test_ldap_directory_api.py`

**Steps:**

1. 添加 `ldap3` 依赖，并用 fake client/依赖注入编写失败测试，覆盖 LDAPS、证书验证、超时、绑定失败、查询权限不足和 AD 分页 cookie。
2. 运行两个目标测试文件，确认失败且测试不访问真实 AD。
3. 实现连接工厂：LDAP/LDAPS、连接超时、证书校验、服务账号绑定；所有异常转换为稳定错误码，不记录凭据。
4. 实现 `POST /admin/ldap/test`，分别验证绑定和最小用户查询，成功后记录配置指纹及测试时间。
5. 实现 `GET /admin/ldap/directory-users?q=&page=&page_size=`，仅返回映射后的姓名、账号、工号、邮箱、手机号、部门、稳定标识、DN 和 AD 启用状态。
6. 对 AD `objectGUID` 做统一字符串编码；实现 LDAP 查询值的字节、空值和多值归一化。
7. 运行两个目标测试文件，确认分页、过滤、脱敏和错误契约通过。
8. 交付检查点：仅在主上明确确认后提交本任务文件。

### Task 4: 实现匹配、绑定和批量同步

**Files:**
- Create: `backend/app/models/ldap_sync.py`
- Create: `backend/app/services/ldap_sync_service.py`
- Create: `backend/alembic/versions/20260910_003_add_ldap_sync_runs.py`
- Modify: `backend/app/views/ldap_view.py`
- Modify: `backend/app/controllers/ldap_controller.py`
- Test: `backend/tests/test_ldap_sync_service.py`
- Test: `backend/tests/test_ldap_sync_api.py`

**Steps:**

1. 编写失败测试覆盖匹配优先级：稳定标识、唯一工号、唯一用户名/邮箱、跨用户冲突和无匹配。
2. 运行 `cd backend; pytest tests/test_ldap_sync_service.py tests/test_ldap_sync_api.py -q`，确认失败。
3. 为目录用户响应增加 `sync_status`、`matched_user` 和冲突原因；查询阶段只建议匹配，不修改数据库。
4. 实现 `POST /admin/ldap/sync`：接受所选稳定标识及明确的绑定决定；新建 LDAP 用户或更新原用户，保留用户 ID 和关系。
5. LDAP 新用户的 `password_hash` 使用不可登录的随机占位值，所有认证必须按 `auth_source` 分流，避免误走本地密码。
6. 建立同步运行与逐项结果记录；批量同步使用逐项事务/保存点，单项失败不回滚成功项。
7. 只有成功查询并明确确认用户不存在、禁用或移出范围时才禁用本地 LDAP 用户；网络/查询失败不得批量禁用。
8. 运行目标测试，确认新建、绑定、更新、冲突和部分失败行为通过。
9. 交付检查点：仅在主上明确确认后提交本任务文件。

### Task 5: 接入 AD 登录认证

**Files:**
- Create: `backend/app/services/ldap_auth_service.py`
- Modify: `backend/app/services/user_service.py`
- Modify: `backend/app/controllers/auth_controller.py`
- Modify: `backend/app/controllers/user_controller.py`
- Modify: `backend/app/core/security.py`
- Modify: `backend/app/core/api_error_contract.py`
- Test: `backend/tests/test_ldap_auth.py`
- Test: `backend/tests/test_user_api.py`

**Steps:**

1. 编写失败测试：本地用户仍走本地哈希；LDAP 用户走用户 DN 绑定；未同步/禁用用户拒绝；LDAP 故障与凭据错误区分内部错误但不泄漏账号信息；LDAP 用户不能改密或重置密码。
2. 运行目标测试并确认失败。
3. 将 `authenticate_user` 按 `auth_source` 分流；LDAP 分支只把本次请求密码传给 LDAP client，不持久化。
4. LDAP 凭据错误继续返回统一“账号或密码错误”；目录不可用返回“目录服务暂时不可用”，使用 503 状态。
5. 修改令牌创建函数支持传入有效期；LDAP 用户签发不超过 8 小时的令牌，本地用户维持现有配置。
6. 禁止 LDAP 用户调用修改密码和管理员重置密码接口；前端根据 `auth_source` 隐藏对应操作。
7. 运行目标测试和现有认证测试，确认无本地登录回归。
8. 交付检查点：仅在主上明确确认后提交本任务文件。

### Task 6: 完成 LDAP 管理页面双栏交互

**Files:**
- Modify: `frontend/src/api/ldap.js`
- Modify: `frontend/src/views/LdapIntegrationView.vue`
- Create: `frontend/src/views/ldapIntegrationView.test.mjs`
- Modify: `frontend/src/utils/adminModules.test.mjs`

**Steps:**

1. 写失败的源契约/行为测试，覆盖双栏结构、连接测试门槛、搜索分页、多选、同步按钮、匹配状态和冲突确认。
2. 运行 `cd frontend; npm test -- ldapIntegrationView adminModules`，确认失败。
3. 完善 API：配置读取/保存、测试连接、目录用户分页查询、批量同步和已绑定用户手动同步。
4. 重构页面左侧为连接、查询账号、用户查询、字段映射；协议变化时仅在端口仍为旧默认值时自动切换 389/636。
5. 右侧实现搜索、刷新、分页、多选、状态标签和同步结果；配置未测试时显示空状态并禁用查询。
6. 对“可绑定”展示现有用户对比确认；冲突用户不可选择并显示原因；已同步用户支持手动刷新。
7. 添加稳定的加载、空数据、部分失败和网络错误状态；保证 720px 以下上下排列且内容不溢出。
8. 运行目标测试及 `npm run build`，确认通过。
9. 交付检查点：仅在主上明确确认后提交本任务文件。

### Task 7: 增加每周同步任务与审计

**Files:**
- Create: `backend/app/jobs/ldap_jobs.py`
- Modify: `backend/app/core/scheduler.py`
- Modify: `backend/app/controllers/ldap_controller.py`
- Test: `backend/tests/test_scheduler_jobs.py`
- Test: `backend/tests/test_ldap_sync_job.py`

**Steps:**

1. 写失败测试：每周日 2:00 调度；任务只处理已绑定用户；手工触发记录操作人；临时 LDAP 故障不禁用用户。
2. 运行两个目标测试文件，确认失败。
3. 扩展调度器支持 `weekday`，保留现有每日任务行为不变。
4. 实现每周同步作业，通过独立数据库会话调用同步服务，并阻止同一任务并发执行。
5. 实现 `POST /admin/ldap/sync-bound-users` 和同步历史查询接口，系统管理员可手动触发及查看结果。
6. 运行调度与同步任务测试，确认通过。
7. 交付检查点：仅在主上明确确认后提交本任务文件。

### Task 8: 全量验证与部署说明

**Files:**
- Modify: `backend/.env.example`（若仓库存在；不存在则修改对应部署环境示例）
- Modify: `README.md`

**Steps:**

1. 记录 `INTEGRATION_ENCRYPTION_KEY`、LDAPS 证书、只读服务账号、默认 AD 属性和迁移顺序。
2. 运行 `cd backend; pytest -q`，预期全量通过。
3. 运行 `cd frontend; npm test`，预期全量通过。
4. 运行 `cd frontend; npm run build`，预期构建成功，仅允许已知的包体积警告。
5. 使用测试 AD 或隔离目录执行验收：保存配置、测试连接、查询用户、补录工号、绑定现有用户、新建 LDAP 用户、AD 登录、AD 禁用后拒绝登录、手动同步。
6. 检查日志和 API 响应，确认不存在绑定密码、用户密码或加密密文。
7. 检查 `git diff`，确保不包含工作区内与 LDAP 无关的既有改动。
8. 根据当时 Git 分支、主分支、远程和上游状态向主上提供实际可用的交付选项，未经明确确认不提交、推送、合并或创建 PR。

### Task 9: 简化用户查询配置

**Files:**
- Modify: `backend/app/controllers/ldap_controller.py`
- Modify: `backend/app/services/ldap_config_service.py`
- Modify: `backend/app/services/ldap_client.py`
- Modify: `frontend/src/views/LdapIntegrationView.vue`
- Test: `backend/tests/test_ldap_client.py`
- Test: `backend/tests/test_ldap_directory_api.py`
- Test: `frontend/src/views/ldapIntegrationView.test.mjs`

**Steps:**

1. 新增失败测试，确认页面不再呈现“用户筛选器”，查询范围控件位于右侧列表上方，并且目录接口接受临时查询范围和禁用账号条件。
2. 运行后端目录查询目标测试与 `cd frontend; node --test src/views/ldapIntegrationView.test.mjs`，确认测试失败。
3. 移除左侧“用户查询”配置组及筛选器校验，保留固定 `(&(objectCategory=person)(objectClass=user))` 作为内部配置值。
4. 扩展目录查询接口，允许本次请求覆盖用户 Base DN 和排除禁用账号选项，但不修改已保存配置及测试指纹。
5. 在右侧列表上方增加查询范围控件；点击“查询”应用草稿条件，刷新和翻页沿用最近一次已应用条件。
6. 将页头操作区设置为与内容区一致的双栏网格，使“同步历史”左边缘与 AD 用户面板左边界对齐，并为窄屏提供自适应布局。
7. 再次运行前后端目标测试，确认通过。
8. 运行前端全量测试、后端 LDAP 目标测试和生产构建，确认无回归。
9. 交付检查点：仅在主上明确确认后提交本任务文件。
