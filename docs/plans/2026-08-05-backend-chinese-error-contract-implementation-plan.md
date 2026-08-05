# 后端中文错误响应契约实施计划

## 目标

将用户可见的 API 失败响应统一为后端提供的错误码和中文 `message`，前端只负责展示，不维护业务错误文案映射。

## 实施项

1. 新增后端错误契约模块，转换旧字符串错误、规范化结构化错误，并生成参数校验响应。
2. 在 FastAPI 应用注册 `HTTPException` 与 `RequestValidationError` 的全局处理器。
3. 为历史英文错误建立服务端术语目录；未登记英文术语作为缺陷暴露。
4. 在 Axios 拦截器保存统一的 `apiMessage` 和 `apiErrorCode`。
5. 删除权限工具中的英文文案映射，更新详情页、后台页和工作流条件分支读取结构化消息或错误码。
6. 补充契约、守卫和前端源码契约测试。

## 验证

- `pytest backend/tests/test_api_error_contract.py backend/tests/test_workflow_runtime_api.py::test_scoped_workflow_does_not_fallback_to_system_action backend/tests/test_business_components_api.py backend/tests/test_bug_workflow_api.py -q`
- `npm test` 与 `npm run build` 在合并到主工作树后执行。
- `git diff --check`

## 交付边界

- 不引入前端国际化框架。
- 不新增前端错误码到中文文案的映射。
- 不为未登记的英文业务错误返回“操作失败”等泛化兜底文案。
