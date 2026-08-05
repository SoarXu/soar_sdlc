# 后端中文错误响应契约设计

## 背景

接口失败响应此前同时存在英文字符串 `detail`、部分结构化对象和 FastAPI 参数校验数组。页面若直接展示 `detail`，会出现英文提示或无法渲染对象。

本设计不引入前端国际化，也不在前端维护错误码到中文文案的映射。用户可见的业务错误由后端提供错误码和中文 `message`。

## 响应契约

所有 `HTTPException` 和请求参数校验错误均使用以下响应形态：

```json
{
  "detail": {
    "code": "ITERATION_NOT_FOUND",
    "message": "未找到迭代"
  }
}
```

- `code` 为稳定的大写下划线标识；既有结构化错误的业务码保持不变。
- `message` 为后端生成的中文用户提示。
- `detail` 中既有的计数、阻塞项等附加字段完整保留。
- 旧字符串错误由后端术语目录转换；核心错误保留语义化业务码，其余历史错误使用基于规范化错误文本的稳定 `LEGACY_ERROR_*` 码。
- 未登记的英文术语直接触发实现缺陷，不返回泛化中文兜底文案。

## 后端设计

新增 `backend/app/core/api_error_contract.py`：

1. 规范化字符串和结构化 `detail`。
2. 将历史英文消息转换为中文，保留并校验结构化错误的 `code`、`message` 与附加字段。
3. 为未带错误码的历史结构化错误补齐稳定码。
4. 为 `RequestValidationError` 返回统一的 `REQUEST_VALIDATION_ERROR` 与中文提示。

在 `backend/app/main.py` 注册全局 `HTTPException` 和 `RequestValidationError` 处理器，保持原 HTTP 状态码。

## 前端设计

Axios 响应拦截器只从 `response.data.detail` 提取：

- `detail.message` 写入 `error.apiMessage`；
- `detail.code` 写入 `error.apiErrorCode`；
- 原始 `detail` 保留给需要读取业务附加字段或错误码的页面。

`actionErrorMessage()` 只返回上述统一中文消息或结构化 `detail.message`，移除英文到中文文案映射。详情页和后台页面复用该入口；项目关闭阻断、代处理原因等条件分支改为读取后端错误码。

## 验证策略

- 契约测试覆盖历史字符串、结构化附加字段、全局 HTTP 处理和参数校验处理。
- 守卫测试扫描静态与插值形式的 `HTTPException` 消息，确保均可转换为不含英文的中文提示。
- 前端测试验证响应拦截器、权限工具和工作流条件分支不再依赖英文消息匹配或前端文案映射。
