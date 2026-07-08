from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controllers.router import api_router
from app.core.config import settings
from app.core.scheduler import scheduler_lifespan
from app.db.session import Base, engine
from app.db.schema import ensure_runtime_schema


def create_app() -> FastAPI:
    ensure_runtime_schema(engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI(title=settings.app_name, lifespan=scheduler_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
