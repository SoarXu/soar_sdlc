"""Normalize user-facing API errors into the backend-owned error contract."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError


_ASCII_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_]*")

# Keep legacy error translations in the backend.  The frontend deliberately has
# no error-code-to-copy dictionary: it only renders the message in this contract.
_LEGACY_PHRASES = {
    "Incorrect username or password": "用户名或密码错误",
    "Not authenticated": "请先登录",
    "System administrator role required": "需要系统管理员权限",
    "Iteration not found": "未找到迭代",
    "Project not found": "未找到项目",
    "Requirement not found": "未找到需求",
    "Task not found": "未找到任务",
    "Bug not found": "未找到缺陷",
    "Test case not found": "未找到测试用例",
    "Test run not found": "未找到测试单",
    "Test run case not found": "未找到测试单用例",
    "User not found": "未找到用户",
    "Role not found": "未找到角色",
    "Workflow definition not found": "未找到工作流定义",
    "Workflow scheme not found": "未找到工作流方案",
    "Business component not found": "未找到业务组件",
    "Work item not found": "未找到工作项",
    "Workflow object not found": "未找到工作流对象",
    "Object not found": "未找到对象",
    "Repository not found": "未找到代码仓库",
    "Commit not found": "未找到提交记录",
    "Jenkins job not found": "未找到构建任务",
    "Exception rule not found": "未找到异常规则",
    "Assignee rule config not found": "未找到处理人规则配置",
    "Workflow component not found": "未找到工作流组件",
    "Git platform connection not found": "未找到代码平台连接",
    "System template source not found": "未找到系统模板来源",
    "Workflow scheme source not found": "未找到工作流方案来源",
    "Linked source not found": "未找到关联来源",
    "Project is required": "项目为必填项",
    "Name is required": "名称为必填项",
    "Scope id is required": "范围编号为必填项",
    "Next handler is required": "请选择下一处理人",
    "Delegate reason is required": "请填写代处理原因",
    "Unsupported workflow trigger configuration": "不支持的工作流触发器配置",
    "System workflow transition cannot be executed manually": "系统工作流动作不能手动执行",
    "Reclassification reason is required": "请填写重新分类原因",
    "Confirmation handler is required": "请选择确认处理人",
    "Selected target state is required": "请选择目标状态",
    "Target roles are required": "请选择目标角色",
    "Initial state is required": "请设置初始状态",
    "Template source is required": "请选择模板来源",
    "Role key is required": "角色标识为必填项",
    "bug_type is required": "缺陷类型为必填项",
    "effective_time is required": "生效时间为必填项",
    "target_iteration_id must be a number": "目标迭代编号必须为数字",
    "target_iteration_id must be a positive integer": "目标迭代编号必须为正整数",
    "Please select an eligible handler": "请选择符合条件的处理人",
    "No access to target iteration project": "没有目标迭代项目的访问权限",
    "Project is closed": "项目已关闭",
    "Project workflow scheme is not enabled": "项目绑定的工作流方案未启用",
    "Workflow scheme must be enabled": "工作流方案必须已启用",
    "Workflow transition not available": "当前状态不支持该工作流操作",
    "Workflow transition not available for current handler state": "当前处理人状态不支持该工作流操作",
    "Only current handler can execute transition": "仅当前处理人可以执行该流转",
    "Transition role not allowed": "当前角色无权执行该流转",
    "Only failed test results can create bugs": "仅失败的测试结果可以创建缺陷",
    "Closed iteration cannot accept bugs": "已结束的迭代不能新增缺陷",
    "Iteration is completed or canceled": "迭代已完成或已取消",
    "Iteration is not in project scope": "迭代不在项目范围内",
    "Iteration is outside bug project scope": "迭代不在缺陷项目范围内",
    "Target iteration cannot be current iteration": "目标迭代不能为当前迭代",
    "Source project must be closed": "来源项目必须已关闭",
    "Business component is disabled": "业务组件已停用",
    "Terminal work items cannot migrate workflow": "已结束工作项不能迁移工作流",
    "Terminal projects cannot create business components": "已结束项目不能创建业务组件",
    "Terminal projects cannot update business components": "已结束项目不能修改业务组件",
    "Unsupported work item type": "不支持的工作项类型",
    "Unsupported workflow object type": "不支持的工作流对象类型",
    "Unsupported workflow validator configuration": "不支持的工作流校验配置",
    "Unsupported workflow notification receiver": "不支持的工作流通知接收人",
    "Unknown workflow object type": "未知的工作流对象类型",
    "Unknown workflow scope type": "未知的工作流范围类型",
    "Unknown state category": "未知的状态分类",
    "Unknown terminal kind": "未知的结束类型",
    "Unknown routing mode": "未知的路由模式",
    "Unknown handler source type": "未知的处理人来源类型",
    "Unknown route dictionary": "未知的路由字典",
}

_LEGACY_TERMS = {
    "access": "访问", "active": "启用", "allow": "允许", "already": "已", "and": "及",
    "assignment": "分派", "automatic": "自动", "available": "可用", "below": "下", "blank": "空白",
    "branch": "分支", "bulk": "批量", "button": "按钮", "cannot": "不能", "case": "用例",
    "change": "变更", "child": "子", "cloned": "克隆的", "closed": "已关闭", "comment": "评论",
    "component": "组件", "condition": "条件", "config": "配置", "configuration": "配置", "conflicts": "冲突",
    "contains": "存在", "context": "上下文", "create": "创建", "creation": "创建", "current": "当前",
    "default": "默认", "definition": "定义", "deleted": "删除", "descendant": "后代", "diagram": "图形",
    "dictionary": "字典", "disabled": "已停用", "does": "", "duplicate": "重复", "during": "期间",
    "eligible": "符合条件的", "enabled": "已启用", "execution": "执行", "failed": "失败", "fallback": "兜底",
    "field": "字段", "fields": "字段", "for": "", "form": "表单", "from": "来源", "has": "存在",
    "handler": "处理人", "hierarchy": "层级", "id": "编号", "in": "", "incomplete": "不完整",
    "initial": "初始", "integrity": "完整性", "invalid": "无效", "is": "", "item": "工作项",
    "items": "工作项", "iteration": "迭代", "kind": "类型", "linked": "关联", "member": "成员",
    "members": "成员", "membership": "成员关系", "mention": "提及", "mentioned": "被提及的", "missing": "缺少",
    "must": "必须", "name": "名称", "no": "无", "notification": "通知", "not": "不",
    "object": "对象", "of": "", "only": "仅", "option": "选项", "options": "选项", "or": "或",
    "outside": "超出", "override": "覆盖", "owner": "负责人", "parent": "父", "password": "密码",
    "persisted": "已保存", "permission": "权限", "pool": "池", "primary": "主", "program": "项目集", "project": "项目",
    "projects": "项目", "recovery": "恢复", "references": "引用", "related": "关联", "requirement": "需求",
    "required": "必填", "requires": "需要", "retry": "重试", "role": "角色", "roles": "角色",
    "route": "路由", "routes": "路由", "routing": "路由", "runnable": "可运行", "run": "测试单",
    "scheme": "方案", "schemes": "方案", "select": "选择", "selected": "所选", "source": "来源",
    "sources": "来源", "state": "状态", "static": "静态", "still": "仍", "support": "支持",
    "supported": "支持", "system": "系统", "target": "目标", "task": "任务", "template": "模板",
    "terminal": "结束", "test": "测试", "the": "", "this": "此", "to": "", "transition": "流转", "delivery": "交付", "manage": "管理",
    "transitions": "流转", "type": "类型", "ui": "界面", "unavailable": "不可用", "unknown": "未知",
    "unsupported": "不支持", "update": "更新", "user": "用户", "validator": "校验", "watch": "关注",
    "with": "", "workflow": "工作流", "work": "工作", "bug": "缺陷", "excel": "表格文件",
    "git": "代码平台", "http": "网页", "jenkins": "构建", "url": "网址", "s": "", "time": "时间",
    "effective_time": "生效时间", "target_iteration_id": "目标迭代编号", "bug_type": "缺陷类型",
}

_LEGACY_TERMS.update({
    "a": "", "accept": "接受", "actions": "操作", "administrators": "管理员", "administrator": "管理员", "ambiguous": "存在歧义",
    "absolute": "绝对", "allowed": "允许", "also": "也", "an": "", "are": "", "assigned": "已关联",
    "at": "", "be": "", "belong": "属于", "business": "业务", "can": "可以",
    "because": "因为", "beneath": "位于", "blockers": "阻塞项", "canonical": "规范", "characters": "字符", "changed": "已变更", "check": "检查",
    "command": "命令", "connection": "连接", "dedicated": "专用", "defer": "延期", "detected": "已发现", "endpoint": "接口", "every": "每个",
    "import": "导入", "instead": "改为", "integers": "整数", "its": "其", "key": "标识", "least": "至少",
    "blocker": "阻塞项", "components": "组件", "cycle": "循环", "delete": "删除", "disable": "停用", "directly": "直接",
    "empty": "空", "exists": "已存在", "found": "找到", "graph": "图",
    "group": "组", "ids": "编号", "incorrect": "错误", "list": "列表",
    "match": "匹配", "moved": "移动", "mutation": "修改", "next": "下一", "non": "非", "one": "一个", "own": "自身", "owned": "归属的",
    "operation": "操作", "owners": "负责人", "platform": "平台", "reason": "原因",
    "refresh": "刷新", "requirement_implementation": "需求实现", "scope": "范围", "start": "启动", "status": "状态",
    "tasks": "任务", "them": "它们", "unclosed": "未关闭", "unfinished": "未完成", "unique": "唯一", "updated": "更新", "use": "使用", "valid": "有效", "value": "值",
    "xlsx": "表格文件",
})


def normalize_http_exception_detail(exc: HTTPException) -> dict[str, Any]:
    """Return a complete, user-facing error contract for an HTTP exception."""
    return normalize_error_detail(exc.detail)


def normalize_error_detail(detail: Any) -> dict[str, Any]:
    if isinstance(detail, Mapping):
        normalized = dict(detail)
        message = normalized.get("message")
        assert isinstance(message, str) and message.strip(), "structured error requires a message"
        normalized["message"] = _to_chinese_message(message)
        normalized.setdefault("code", _legacy_error_code(message))
        assert _is_contract_code(normalized["code"]), "structured error requires a valid code"
        return normalized

    assert isinstance(detail, str) and detail.strip(), "error detail must be a non-empty string or object"
    return {
        "code": _legacy_error_code(detail),
        "message": _to_chinese_message(detail),
    }


def request_validation_detail(exc: RequestValidationError) -> dict[str, str]:
    # FastAPI's default messages are English and implementation-oriented. The
    # response deliberately keeps the public explanation short and stable.
    return {
        "code": "REQUEST_VALIDATION_ERROR",
        "message": "请求参数不符合要求",
    }


def _to_chinese_message(message: str) -> str:
    if not _contains_ascii_letters(message):
        return message
    translated = _LEGACY_PHRASES.get(message)
    if translated:
        return translated

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(0)
        replacement = _LEGACY_TERMS.get(token.lower())
        if replacement is None:
            raise AssertionError(f"unregistered legacy error term: {token} in {message!r}")
        return replacement

    translated = _ASCII_TOKEN.sub(replace_token, message)
    if _contains_ascii_letters(translated):
        raise AssertionError(f"unregistered legacy error: {message!r}")
    return re.sub(r"\s+", "", translated).strip()


def _legacy_error_code(message: str) -> str:
    if message == "Iteration not found":
        return "ITERATION_NOT_FOUND"
    if message == "Project not found":
        return "PROJECT_NOT_FOUND"
    if message == "Requirement not found":
        return "REQUIREMENT_NOT_FOUND"
    if message == "Task not found":
        return "TASK_NOT_FOUND"
    if message == "Bug not found":
        return "BUG_NOT_FOUND"
    if message == "Test case not found":
        return "TEST_CASE_NOT_FOUND"
    if message == "Test run not found":
        return "TEST_RUN_NOT_FOUND"
    if message == "Not authenticated":
        return "NOT_AUTHENTICATED"
    if message == "Incorrect username or password":
        return "INVALID_CREDENTIALS"
    if message == "Delegate reason is required":
        return "DELEGATE_REASON_REQUIRED"
    if message.startswith("Project has unfinished ") and message.endswith(" blockers"):
        return "PROJECT_HAS_UNFINISHED_ITEMS"
    digest = hashlib.sha256(_error_signature(message).encode("utf-8")).hexdigest()[:12].upper()
    return f"LEGACY_ERROR_{digest}"


def _error_signature(message: str) -> str:
    return re.sub(r"\b\d+\b", "{number}", message.strip())


def _contains_ascii_letters(value: str) -> bool:
    return any(char.isascii() and char.isalpha() for char in value)


def _is_contract_code(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Z][A-Z0-9_]*", value))
