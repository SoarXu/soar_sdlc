import logging
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers.router import api_router
from app.core.api_error_contract import normalize_http_exception_detail, request_validation_detail
from app.core.config import settings
from app.core.scheduler import scheduler_lifespan
from app.db.session import Base, engine, query_metrics_scope
from app.db.schema import ensure_runtime_schema


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)

    app = FastAPI(title=settings.app_name, lifespan=scheduler_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    performance_logger = logging.getLogger("app.performance")

    @app.middleware("http")
    async def record_slow_api_request(request: Request, call_next):
        started_at = perf_counter()
        status_code = 500
        with query_metrics_scope() as metrics:
            try:
                response = await call_next(request)
                status_code = response.status_code
                return response
            finally:
                elapsed_ms = (perf_counter() - started_at) * 1000
                if request.url.path.startswith("/api/") and elapsed_ms >= settings.slow_api_request_ms:
                    performance_logger.warning(
                        "slow_api_request",
                        extra={
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": status_code,
                            "elapsed_ms": round(elapsed_ms, 1),
                            "query_count": metrics.query_count,
                            "database_time_ms": round(metrics.database_time_ms, 1),
                        },
                    )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": normalize_http_exception_detail(exc)})

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": request_validation_detail(exc)})

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
