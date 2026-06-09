# 智享生物 SDLC 数据字典（MySQL 8.0）

## 1. 设计约定

数据库基准：MySQL 8.0。

通用规则：

- 所有业务主表使用 `BIGINT UNSIGNED AUTO_INCREMENT` 作为主键。
- 页面展示编号由对象类型前缀 + 自增 ID 生成，例如 `REQ-102`、`TASK-230`、`BUG-88`。
- 不使用 `REQ-001` 这类字符串作为数据库主键。
- 核心字段放在业务主表，自定义字段放在 `custom_field_value`。
- 通用关系放在 `object_relation`。
- 删除优先使用软删除字段 `delete_time`。
- JSON 字段用于配置、快照、扩展信息。
- 时间字段统一使用 `DATETIME`。

通用审计字段：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| creator_id | BIGINT UNSIGNED | NULL | 创建人 ID |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 ID |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

## 2. 用户与权限

### 2.1 users 用户表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 用户 ID |
| username | VARCHAR(64) | NOT NULL, UNIQUE | 登录账号 |
| full_name | VARCHAR(100) | NOT NULL | 姓名 |
| email | VARCHAR(128) | NULL | 邮箱 |
| mobile | VARCHAR(32) | NULL | 手机号 |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希 |
| department | VARCHAR(100) | NULL | 部门 |
| is_active | TINYINT(1) | NOT NULL DEFAULT 1 | 是否启用 |
| last_login_time | DATETIME | NULL | 最近登录时间 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

索引：

- `uk_users_username(username)`
- `idx_users_full_name(full_name)`

### 2.2 roles 角色表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 角色 ID |
| role_key | VARCHAR(64) | NOT NULL, UNIQUE | 角色标识 |
| role_name | VARCHAR(100) | NOT NULL | 角色名称 |
| description | VARCHAR(500) | NULL | 描述 |
| is_system | TINYINT(1) | NOT NULL DEFAULT 0 | 是否系统角色 |
| enabled | TINYINT(1) | NOT NULL DEFAULT 1 | 是否启用 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

### 2.3 user_roles 用户角色关系表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 主键 |
| user_id | BIGINT UNSIGNED | NOT NULL | 用户 ID |
| role_id | BIGINT UNSIGNED | NOT NULL | 角色 ID |
| create_time | DATETIME | NOT NULL | 创建时间 |

索引：

- `uk_user_roles_user_role(user_id, role_id)`

### 2.4 project_members 项目成员表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 主键 |
| project_id | BIGINT UNSIGNED | NOT NULL | 项目 ID |
| user_id | BIGINT UNSIGNED | NOT NULL | 用户 ID |
| project_role | VARCHAR(64) | NOT NULL | 项目角色：owner、developer、tester、viewer |
| join_time | DATETIME | NOT NULL | 加入时间 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

索引：

- `uk_project_members_project_user(project_id, user_id)`
- `idx_project_members_user(user_id)`

## 3. 项目管理

### 3.1 programs 项目集表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 项目集 ID |
| parent_id | BIGINT UNSIGNED | NULL | 父项目集 ID |
| name | VARCHAR(150) | NOT NULL | 项目集名称 |
| owner_id | BIGINT UNSIGNED | NULL | 负责人 ID |
| department | VARCHAR(100) | NULL | 所属部门 |
| planned_start_date | DATE | NULL | 计划开始日期 |
| planned_end_date | DATE | NULL | 计划结束日期，长期维护项目集为空 |
| is_long_term | TINYINT(1) | NOT NULL DEFAULT 0 | 是否长期维护 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'active' | 状态 |
| description | TEXT | NULL | 描述 |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

索引：

- `idx_programs_owner(owner_id)`
- `idx_programs_parent(parent_id)`
- `idx_programs_status(status)`

### 3.2 projects 项目表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 项目 ID |
| program_id | BIGINT UNSIGNED | NULL | 所属项目集 ID |
| name | VARCHAR(150) | NOT NULL | 项目名称 |
| owner_id | BIGINT UNSIGNED | NULL | 项目负责人 ID |
| start_date | DATE | NULL | 开始日期 |
| end_date | DATE | NULL | 结束日期 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'active' | 状态 |
| description | TEXT | NULL | 描述 |
| workflow_config_id | BIGINT UNSIGNED | NULL | 项目级工作流配置 ID |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

索引：

- `idx_projects_program(program_id)`
- `idx_projects_owner(owner_id)`
- `idx_projects_status(status)`

### 3.3 iterations 迭代表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 迭代 ID |
| project_id | BIGINT UNSIGNED | NOT NULL | 所属项目 ID |
| name | VARCHAR(150) | NOT NULL | 迭代名称 |
| owner_id | BIGINT UNSIGNED | NULL | 负责人 ID |
| start_date | DATE | NULL | 开始日期 |
| end_date | DATE | NULL | 结束日期 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'planning' | 状态：planning、active、finished、closed |
| goal | TEXT | NULL | 目标说明 |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

索引：

- `idx_iterations_project(project_id)`
- `idx_iterations_owner(owner_id)`
- `idx_iterations_status(status)`

## 4. 需求与任务

### 4.1 requirements 需求表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 需求 ID |
| project_id | BIGINT UNSIGNED | NOT NULL | 所属项目 ID |
| iteration_id | BIGINT UNSIGNED | NULL | 所属迭代 ID |
| title | VARCHAR(255) | NOT NULL | 需求标题 |
| requirement_type | VARCHAR(64) | NULL | 需求类型 |
| priority | VARCHAR(32) | NOT NULL DEFAULT 'medium' | 优先级 |
| owner_id | BIGINT UNSIGNED | NULL | 负责人 ID |
| proposer_id | BIGINT UNSIGNED | NULL | 提出人 ID |
| status | VARCHAR(32) | NOT NULL DEFAULT 'draft' | 状态：draft、active、done、closed |
| review_status | VARCHAR(32) | NOT NULL DEFAULT 'not_required' | 评审状态 |
| description | TEXT | NULL | 需求描述 |
| acceptance_criteria | TEXT | NULL | 验收标准 |
| source_reviewed | TINYINT(1) | NOT NULL DEFAULT 0 | 是否评审通过 |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

索引：

- `idx_requirements_project(project_id)`
- `idx_requirements_iteration(iteration_id)`
- `idx_requirements_owner(owner_id)`
- `idx_requirements_status(status)`

### 4.2 tasks 任务表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 任务 ID |
| project_id | BIGINT UNSIGNED | NOT NULL | 所属项目 ID |
| requirement_id | BIGINT UNSIGNED | NULL | 关联需求 ID |
| title | VARCHAR(255) | NOT NULL | 任务标题 |
| task_type | VARCHAR(64) | NULL | 任务类型 |
| priority | VARCHAR(32) | NOT NULL DEFAULT 'medium' | 优先级 |
| owner_id | BIGINT UNSIGNED | NULL | 负责人 ID |
| estimated_hours | DECIMAL(10,2) | NULL | 预计工时 |
| actual_hours | DECIMAL(10,2) | NULL | 实际工时 |
| due_date | DATE | NULL | 截止日期 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'todo' | 状态：todo、doing、done、closed |
| description | TEXT | NULL | 任务描述 |
| source_requirement_review_status | VARCHAR(32) | NULL | 生成任务时需求评审状态快照 |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

索引：

- `idx_tasks_project(project_id)`
- `idx_tasks_requirement(requirement_id)`
- `idx_tasks_owner(owner_id)`
- `idx_tasks_status(status)`

## 5. 测试管理

### 5.1 test_cases 测试用例表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 用例 ID |
| project_id | BIGINT UNSIGNED | NULL | 所属项目 ID，NULL 表示全局用例 |
| requirement_id | BIGINT UNSIGNED | NULL | 关联需求 ID |
| title | VARCHAR(255) | NOT NULL | 用例标题 |
| case_type | VARCHAR(64) | NULL | 用例类型 |
| priority | VARCHAR(32) | NOT NULL DEFAULT 'medium' | 优先级 |
| default_tester_id | BIGINT UNSIGNED | NULL | 默认测试人员 |
| precondition | TEXT | NULL | 前置条件 |
| steps_json | JSON | NULL | 测试步骤，结构化 JSON |
| expected_result | TEXT | NULL | 预期结果 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'active' | 状态 |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

索引：

- `idx_test_cases_project(project_id)`
- `idx_test_cases_requirement(requirement_id)`
- `idx_test_cases_tester(default_tester_id)`

### 5.2 test_runs 测试单表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 测试单 ID |
| project_id | BIGINT UNSIGNED | NOT NULL | 所属项目 ID |
| iteration_id | BIGINT UNSIGNED | NULL | 关联迭代 ID |
| name | VARCHAR(150) | NOT NULL | 测试单名称 |
| test_owner_id | BIGINT UNSIGNED | NULL | 测试负责人 ID |
| start_date | DATE | NULL | 开始日期 |
| end_date | DATE | NULL | 结束日期 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'planning' | 执行状态 |
| remark | TEXT | NULL | 备注 |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

### 5.3 test_run_cases 测试单用例执行表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 主键 |
| test_run_id | BIGINT UNSIGNED | NOT NULL | 测试单 ID |
| test_case_id | BIGINT UNSIGNED | NOT NULL | 测试用例 ID |
| tester_id | BIGINT UNSIGNED | NULL | 执行人 |
| result | VARCHAR(32) | NOT NULL DEFAULT 'not_run' | not_run、passed、failed、blocked |
| execute_time | DATETIME | NULL | 执行时间 |
| remark | TEXT | NULL | 执行备注 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

索引：

- `uk_test_run_cases_run_case(test_run_id, test_case_id)`
- `idx_test_run_cases_result(result)`

## 6. Bug 管理

### 6.1 bugs Bug 表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | Bug ID |
| project_id | BIGINT UNSIGNED | NOT NULL | 所属项目 ID |
| requirement_id | BIGINT UNSIGNED | NULL | 关联需求 ID |
| task_id | BIGINT UNSIGNED | NULL | 关联任务 ID |
| test_case_id | BIGINT UNSIGNED | NULL | 来源用例 ID |
| test_run_id | BIGINT UNSIGNED | NULL | 来源测试单 ID |
| title | VARCHAR(255) | NOT NULL | Bug 标题 |
| severity | VARCHAR(32) | NOT NULL DEFAULT 'medium' | 严重程度 |
| priority | VARCHAR(32) | NOT NULL DEFAULT 'medium' | 优先级 |
| owner_id | BIGINT UNSIGNED | NULL | 负责人 ID |
| reporter_id | BIGINT UNSIGNED | NULL | 提出人 ID |
| reproduce_steps | TEXT | NULL | 复现步骤 |
| expected_result | TEXT | NULL | 期望结果 |
| actual_result | TEXT | NULL | 实际结果 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'open' | open、fixing、verifying、closed、reopened |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |
| delete_time | DATETIME | NULL | 软删除时间 |

索引：

- `idx_bugs_project(project_id)`
- `idx_bugs_requirement(requirement_id)`
- `idx_bugs_task(task_id)`
- `idx_bugs_owner(owner_id)`
- `idx_bugs_status(status)`

## 7. 标签与附件

### 7.1 tags 标签表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 标签 ID |
| tag_name | VARCHAR(64) | NOT NULL | 标签名称 |
| color | VARCHAR(32) | NULL | 标签颜色 |
| object_type | VARCHAR(64) | NOT NULL | 适用对象：test_case、bug |
| enabled | TINYINT(1) | NOT NULL DEFAULT 1 | 是否启用 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

索引：

- `uk_tags_object_name(object_type, tag_name)`

### 7.2 object_tags 对象标签关系表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 主键 |
| object_type | VARCHAR(64) | NOT NULL | 对象类型 |
| object_id | BIGINT UNSIGNED | NOT NULL | 对象 ID |
| tag_id | BIGINT UNSIGNED | NOT NULL | 标签 ID |
| create_time | DATETIME | NOT NULL | 创建时间 |

索引：

- `uk_object_tags_object_tag(object_type, object_id, tag_id)`
- `idx_object_tags_tag(tag_id)`

### 7.3 attachments 附件表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 附件 ID |
| object_type | VARCHAR(64) | NOT NULL | 对象类型 |
| object_id | BIGINT UNSIGNED | NOT NULL | 对象 ID |
| file_name | VARCHAR(255) | NOT NULL | 原始文件名 |
| file_path | VARCHAR(500) | NOT NULL | 存储路径 |
| file_size | BIGINT UNSIGNED | NULL | 文件大小 |
| mime_type | VARCHAR(128) | NULL | MIME 类型 |
| uploader_id | BIGINT UNSIGNED | NULL | 上传人 |
| upload_time | DATETIME | NOT NULL | 上传时间 |

索引：

- `idx_attachments_object(object_type, object_id)`

## 8. 字段注册中心

### 8.1 form_field_registry 字段注册表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 字段 ID |
| object_type | VARCHAR(64) | NOT NULL | 对象类型 |
| field_key | VARCHAR(100) | NOT NULL | 字段唯一标识 |
| field_label | VARCHAR(100) | NOT NULL | 字段显示名称 |
| field_type | VARCHAR(64) | NOT NULL | text、textarea、select、date、user、number、file、richtext、table |
| is_system | TINYINT(1) | NOT NULL DEFAULT 0 | 是否系统字段 |
| is_required | TINYINT(1) | NOT NULL DEFAULT 0 | 是否必填 |
| is_visible | TINYINT(1) | NOT NULL DEFAULT 1 | 是否表单展示 |
| is_searchable | TINYINT(1) | NOT NULL DEFAULT 0 | 是否可搜索 |
| is_list_visible | TINYINT(1) | NOT NULL DEFAULT 0 | 是否列表展示 |
| options_source | VARCHAR(100) | NULL | 选项来源 |
| default_value | VARCHAR(500) | NULL | 默认值 |
| sort_order | INT | NOT NULL DEFAULT 0 | 排序 |
| validation_rules | JSON | NULL | 校验规则 |
| business_key | VARCHAR(64) | NULL | 业务语义标识 |
| enabled | TINYINT(1) | NOT NULL DEFAULT 1 | 是否启用 |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

索引：

- `uk_form_field_object_key(object_type, field_key)`
- `idx_form_field_object(object_type)`

### 8.2 form_layout_config 表单布局配置表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 配置 ID |
| object_type | VARCHAR(64) | NOT NULL | 对象类型 |
| field_id | BIGINT UNSIGNED | NOT NULL | 字段 ID |
| group_name | VARCHAR(100) | NULL | 分组名称 |
| width_span | INT | NOT NULL DEFAULT 24 | 表单栅格宽度 |
| is_advanced | TINYINT(1) | NOT NULL DEFAULT 0 | 是否高级字段 |
| sort_order | INT | NOT NULL DEFAULT 0 | 排序 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

### 8.3 custom_field_value 自定义字段值表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 主键 |
| object_type | VARCHAR(64) | NOT NULL | 对象类型 |
| object_id | BIGINT UNSIGNED | NOT NULL | 对象 ID |
| field_id | BIGINT UNSIGNED | NOT NULL | 字段 ID |
| value_text | TEXT | NULL | 文本值 |
| value_number | DECIMAL(18,4) | NULL | 数字值 |
| value_date | DATETIME | NULL | 日期值 |
| value_json | JSON | NULL | 复杂值 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

索引：

- `uk_custom_field_value(object_type, object_id, field_id)`
- `idx_custom_field_field(field_id)`

## 9. 工作流

### 9.1 workflow_rules 工作流规则表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 规则 ID |
| rule_name | VARCHAR(150) | NOT NULL | 规则名称 |
| scope_type | VARCHAR(32) | NOT NULL | system、project |
| scope_id | BIGINT UNSIGNED | NULL | 项目 ID，系统级为空 |
| target_object | VARCHAR(64) | NOT NULL | 适用对象 |
| trigger_action | VARCHAR(64) | NOT NULL | 触发动作 |
| condition_json | JSON | NULL | 条件配置 |
| action_json | JSON | NOT NULL | 执行动作配置 |
| enabled | TINYINT(1) | NOT NULL DEFAULT 1 | 是否启用 |
| priority | INT | NOT NULL DEFAULT 100 | 优先级 |
| block_message | VARCHAR(500) | NULL | 阻断提示 |
| description | TEXT | NULL | 描述 |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| updater_id | BIGINT UNSIGNED | NULL | 更新人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

索引：

- `idx_workflow_scope(scope_type, scope_id)`
- `idx_workflow_target_action(target_object, trigger_action)`

## 10. 关联关系

### 10.1 object_relation 对象关联表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 关系 ID |
| source_type | VARCHAR(64) | NOT NULL | 来源对象类型 |
| source_id | BIGINT UNSIGNED | NOT NULL | 来源对象 ID |
| target_type | VARCHAR(64) | NOT NULL | 目标对象类型 |
| target_id | BIGINT UNSIGNED | NOT NULL | 目标对象 ID |
| relation_type | VARCHAR(64) | NOT NULL | generated、related、blocked、duplicate、depends_on、covers、executes、fixes |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| create_time | DATETIME | NOT NULL | 创建时间 |

索引：

- `idx_relation_source(source_type, source_id)`
- `idx_relation_target(target_type, target_id)`
- `idx_relation_type(relation_type)`

## 11. 通知与钉钉预留

### 11.1 notifications 站内通知表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 通知 ID |
| receiver_id | BIGINT UNSIGNED | NOT NULL | 接收人 ID |
| title | VARCHAR(200) | NOT NULL | 通知标题 |
| content | TEXT | NULL | 通知内容 |
| object_type | VARCHAR(64) | NULL | 关联对象类型 |
| object_id | BIGINT UNSIGNED | NULL | 关联对象 ID |
| is_read | TINYINT(1) | NOT NULL DEFAULT 0 | 是否已读 |
| read_time | DATETIME | NULL | 阅读时间 |
| create_time | DATETIME | NOT NULL | 创建时间 |

索引：

- `idx_notifications_receiver(receiver_id, is_read)`

### 11.2 notification_channel_config 通知渠道配置表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 渠道 ID |
| channel_type | VARCHAR(32) | NOT NULL | in_app、dingtalk |
| channel_name | VARCHAR(100) | NOT NULL | 渠道名称 |
| webhook_url | VARCHAR(1000) | NULL | 钉钉机器人 Webhook，加密存储 |
| secret | VARCHAR(1000) | NULL | 钉钉加签密钥，加密存储 |
| enabled | TINYINT(1) | NOT NULL DEFAULT 1 | 是否启用 |
| scope_type | VARCHAR(32) | NOT NULL DEFAULT 'system' | system、project、program |
| scope_id | BIGINT UNSIGNED | NULL | 范围 ID |
| creator_id | BIGINT UNSIGNED | NULL | 创建人 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

### 11.3 notification_delivery_log 通知发送记录表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 日志 ID |
| notification_id | BIGINT UNSIGNED | NULL | 站内通知 ID |
| channel_type | VARCHAR(32) | NOT NULL | 通知渠道 |
| receiver | VARCHAR(255) | NULL | 接收目标 |
| request_payload | JSON | NULL | 发送内容 |
| response_body | TEXT | NULL | 返回结果 |
| status | VARCHAR(32) | NOT NULL | success、failed、pending |
| retry_count | INT | NOT NULL DEFAULT 0 | 重试次数 |
| send_time | DATETIME | NULL | 发送时间 |
| create_time | DATETIME | NOT NULL | 创建时间 |

## 12. 审计日志

### 12.1 audit_log 审计日志表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 日志 ID |
| actor_id | BIGINT UNSIGNED | NULL | 操作人 ID |
| action | VARCHAR(64) | NOT NULL | 操作类型 |
| object_type | VARCHAR(64) | NOT NULL | 对象类型 |
| object_id | BIGINT UNSIGNED | NULL | 对象 ID |
| before_data | JSON | NULL | 变更前数据 |
| after_data | JSON | NULL | 变更后数据 |
| ip_address | VARCHAR(64) | NULL | IP 地址 |
| user_agent | VARCHAR(500) | NULL | 浏览器信息 |
| create_time | DATETIME | NOT NULL | 操作时间 |

索引：

- `idx_audit_object(object_type, object_id)`
- `idx_audit_actor(actor_id)`
- `idx_audit_create_time(create_time)`

## 13. GitLab 集成预留

### 13.1 external_integration_mapping 外部系统映射表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AUTO_INCREMENT | 映射 ID |
| provider | VARCHAR(32) | NOT NULL | gitlab、github、jira |
| object_type | VARCHAR(64) | NOT NULL | 本系统对象类型 |
| object_id | BIGINT UNSIGNED | NOT NULL | 本系统对象 ID |
| external_project_id | VARCHAR(128) | NULL | GitLab project ID |
| external_object_type | VARCHAR(64) | NOT NULL | issue、merge_request、commit、pipeline |
| external_object_id | VARCHAR(128) | NULL | GitLab 全局 ID |
| external_iid | VARCHAR(128) | NULL | GitLab 项目内 IID |
| external_url | VARCHAR(1000) | NULL | 外部链接 |
| sync_status | VARCHAR(32) | NOT NULL DEFAULT 'pending' | 同步状态 |
| last_sync_time | DATETIME | NULL | 最近同步时间 |
| create_time | DATETIME | NOT NULL | 创建时间 |
| update_time | DATETIME | NOT NULL | 更新时间 |

索引：

- `idx_external_mapping_local(provider, object_type, object_id)`
- `idx_external_mapping_external(provider, external_project_id, external_object_type, external_iid)`

## 14. 建议枚举值

### 14.1 通用状态

| 对象 | 状态 |
|---|---|
| 项目集 | active、archived |
| 项目 | active、paused、closed |
| 迭代 | planning、active、finished、closed |
| 需求 | draft、active、done、closed |
| 任务 | todo、doing、done、closed |
| 测试用例 | active、disabled |
| 测试单 | planning、running、finished、closed |
| Bug | open、fixing、verifying、closed、reopened |

### 14.2 优先级

| 值 | 说明 |
|---|---|
| low | 低 |
| medium | 中 |
| high | 高 |
| urgent | 紧急 |

### 14.3 Bug 严重程度

| 值 | 说明 |
|---|---|
| low | 低 |
| medium | 中 |
| high | 高 |
| critical | 严重 |

## 15. 关系说明

核心外键关系：

- `projects.program_id -> programs.id`
- `iterations.project_id -> projects.id`
- `requirements.project_id -> projects.id`
- `requirements.iteration_id -> iterations.id`
- `tasks.project_id -> projects.id`
- `tasks.requirement_id -> requirements.id`
- `test_cases.requirement_id -> requirements.id`
- `test_runs.project_id -> projects.id`
- `test_run_cases.test_run_id -> test_runs.id`
- `test_run_cases.test_case_id -> test_cases.id`
- `bugs.project_id -> projects.id`
- `bugs.requirement_id -> requirements.id`
- `bugs.task_id -> tasks.id`
- `bugs.test_case_id -> test_cases.id`
- `bugs.test_run_id -> test_runs.id`

通用弱关系：

- 用 `object_relation` 表表达生成、覆盖、执行、修复、依赖、重复等关系。
- 用 `external_integration_mapping` 表表达与 GitLab 等外部系统的映射。

