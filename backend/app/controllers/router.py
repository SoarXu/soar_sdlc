from fastapi import APIRouter

from app.controllers import (
    auth_controller,
    bug_controller,
    dashboard_controller,
    devops_controller,
    health_controller,
    iteration_controller,
    program_controller,
    project_controller,
    requirement_controller,
    role_controller,
    task_controller,
    test_case_controller,
    test_run_controller,
    user_controller,
    workflow_component_controller,
    workflow_controller,
)


api_router = APIRouter()
api_router.include_router(health_controller.router, tags=["health"])
api_router.include_router(auth_controller.router, prefix="/auth", tags=["auth"])
api_router.include_router(user_controller.router, prefix="/users", tags=["users"])
api_router.include_router(role_controller.router, prefix="/roles", tags=["roles"])
api_router.include_router(dashboard_controller.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(program_controller.router, prefix="/programs", tags=["programs"])
api_router.include_router(project_controller.router, prefix="/projects", tags=["projects"])
api_router.include_router(iteration_controller.router, prefix="/iterations", tags=["iterations"])
api_router.include_router(requirement_controller.router, prefix="/requirements", tags=["requirements"])
api_router.include_router(task_controller.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(test_case_controller.router, prefix="/test-cases", tags=["test-cases"])
api_router.include_router(test_run_controller.router, tags=["test-runs"])
api_router.include_router(bug_controller.router, prefix="/bugs", tags=["bugs"])
api_router.include_router(devops_controller.router, prefix="/devops", tags=["devops"])
api_router.include_router(workflow_controller.router, prefix="/workflow-rules", tags=["workflow-rules"])
api_router.include_router(workflow_component_controller.component_router, prefix="/workflow-components", tags=["workflow-components"])
api_router.include_router(workflow_component_controller.handler_router, prefix="/workflow-handlers", tags=["workflow-handlers"])
