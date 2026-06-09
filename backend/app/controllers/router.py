from fastapi import APIRouter

from app.controllers import (
    auth_controller,
    dashboard_controller,
    health_controller,
    iteration_controller,
    program_controller,
    project_controller,
    requirement_controller,
    task_controller,
)


api_router = APIRouter()
api_router.include_router(health_controller.router, tags=["health"])
api_router.include_router(auth_controller.router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard_controller.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(program_controller.router, prefix="/programs", tags=["programs"])
api_router.include_router(project_controller.router, prefix="/projects", tags=["projects"])
api_router.include_router(iteration_controller.router, prefix="/iterations", tags=["iterations"])
api_router.include_router(requirement_controller.router, prefix="/requirements", tags=["requirements"])
api_router.include_router(task_controller.router, prefix="/tasks", tags=["tasks"])
