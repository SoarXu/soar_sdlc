from fastapi import APIRouter

from app.controllers import (
    assignee_rule_config_controller,
    auth_controller,
    bug_controller,
    bug_type_controller,
    dashboard_controller,
    devops_controller,
    exception_rule_controller,
    health_controller,
    iteration_controller,
    notification_controller,
    object_watch_controller,
    program_controller,
    project_controller,
    requirement_controller,
    role_controller,
    task_controller,
    test_case_controller,
    test_run_controller,
    user_controller,
    work_item_controller,
    work_item_comment_controller,
    workflow_component_controller,
    workflow_definition_controller,
    workflow_runtime_controller,
)


api_router = APIRouter()
api_router.include_router(health_controller.router, tags=["health"])
api_router.include_router(auth_controller.router, prefix="/auth", tags=["auth"])
api_router.include_router(user_controller.router, prefix="/users", tags=["users"])
api_router.include_router(role_controller.router, prefix="/roles", tags=["roles"])
api_router.include_router(
    assignee_rule_config_controller.router,
    prefix="/assignee-rule-configs",
    tags=["assignee-rule-configs"],
)
api_router.include_router(dashboard_controller.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(notification_controller.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(exception_rule_controller.router, prefix="/exception-rules", tags=["exception-rules"])
api_router.include_router(object_watch_controller.router, prefix="/object-watches", tags=["object-watches"])
api_router.include_router(work_item_controller.router, prefix="/work-items", tags=["work-items"])
api_router.include_router(work_item_comment_controller.router, prefix="/work-item-comments", tags=["work-item-comments"])
api_router.include_router(program_controller.router, prefix="/programs", tags=["programs"])
api_router.include_router(project_controller.router, prefix="/projects", tags=["projects"])
api_router.include_router(iteration_controller.router, prefix="/iterations", tags=["iterations"])
api_router.include_router(requirement_controller.router, prefix="/requirements", tags=["requirements"])
api_router.include_router(task_controller.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(test_case_controller.router, prefix="/test-cases", tags=["test-cases"])
api_router.include_router(test_run_controller.router, tags=["test-runs"])
api_router.include_router(bug_controller.router, prefix="/bugs", tags=["bugs"])
api_router.include_router(bug_type_controller.router, prefix="/bug-types", tags=["bug-types"])
api_router.include_router(devops_controller.router, prefix="/devops", tags=["devops"])
api_router.include_router(workflow_definition_controller.router, prefix="/workflow-definitions", tags=["workflow-definitions"])
api_router.include_router(workflow_runtime_controller.router, prefix="/workflow-runtime", tags=["workflow-runtime"])
api_router.include_router(workflow_component_controller.component_router, prefix="/workflow-components", tags=["workflow-components"])
api_router.include_router(workflow_component_controller.handler_router, prefix="/workflow-handlers", tags=["workflow-handlers"])
