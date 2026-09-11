import asyncio
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.analysis_settings import router as analysis_settings_router
from app.api.routes.detections import router as detections_router
from app.api.routes.dataset_approver_assignments import (
    admin_router as dataset_approver_admin_router,
    router as dataset_approver_router,
)
from app.api.routes.demo_interpretation import router as demo_interpretation_router
from app.api.routes.floor_plans import router as floor_plans_router
from app.api.routes.health import router as health_router
from app.api.routes.layouts import router as layouts_router
from app.api.routes.manual_symbols import router as manual_symbols_router
from app.api.routes.processing import router as processing_router
from app.api.routes.project_floors import router as project_floors_router
from app.api.routes.projects import router as projects_router
from app.api.routes.review_images import router as review_images_router
from app.api.routes.symbol_legends import (
    admin_router as symbol_legend_admin_router,
    router as symbol_legends_router,
)
from app.core.config import (
    OAuthOIDCConfigurationError,
    Settings,
    get_cors_allowed_origins,
    get_oauth_oidc_configuration,
    get_settings,
)
from app.workers.demo_worker import run_demo_worker


@asynccontextmanager
async def lifespan(application: FastAPI):
    worker_thread = None
    stop_event = None
    settings = application.state.settings
    if settings.auto_start_demo_worker and settings.app_env == "development":
        stop_event = threading.Event()
        worker_thread = threading.Thread(
            target=run_demo_worker,
            kwargs={
                "stop_event": stop_event,
                "worker_identity": f"demo-worker:{os.getpid()}",
                "settings": settings,
            },
            daemon=True,
            name="ved-demo-worker",
        )
        worker_thread.start()
    try:
        yield
    finally:
        if stop_event is not None:
            stop_event.set()
        if worker_thread is not None:
            await asyncio.to_thread(worker_thread.join, 5)


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or get_settings()
    application = FastAPI(
        title=f"{application_settings.app_name} API",
        debug=application_settings.app_debug,
        lifespan=lifespan,
    )
    application.state.settings = application_settings

    try:
        oauth_configuration = get_oauth_oidc_configuration(application_settings)
    except OAuthOIDCConfigurationError as error:
        application.state.oauth_oidc_configuration = None
        application.state.oauth_oidc_configuration_error = str(error)
    else:
        application.state.oauth_oidc_configuration = oauth_configuration
        application.state.oauth_oidc_configuration_error = None
        application.add_middleware(
            SessionMiddleware,
            secret_key=oauth_configuration.session_secret.get_secret_value(),
            session_cookie="ved_session",
            same_site="lax",
            https_only=application_settings.app_env.casefold() != "development",
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(get_cors_allowed_origins(application_settings)),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
        ],
    )

    application.include_router(health_router)
    application.include_router(analysis_settings_router)
    application.include_router(dataset_approver_router)
    application.include_router(dataset_approver_admin_router)
    application.include_router(demo_interpretation_router)
    application.include_router(auth_router)
    application.include_router(projects_router)
    application.include_router(project_floors_router)
    application.include_router(layouts_router)
    application.include_router(floor_plans_router)
    application.include_router(processing_router)
    application.include_router(detections_router)
    application.include_router(manual_symbols_router)
    application.include_router(review_images_router)
    application.include_router(symbol_legends_router)
    application.include_router(symbol_legend_admin_router)
    return application


app = create_app()
