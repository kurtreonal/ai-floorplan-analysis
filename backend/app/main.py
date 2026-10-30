import asyncio
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from app.api.routes.application_defaults import router as application_defaults_router
from app.api.routes.material_assemblies import router as material_assemblies_router
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.auth_errors import auth_exception_handler, protect_auth_access_logs

from app.api.routes.auth import router as auth_router
from app.api.routes.client_workflow import router as client_workflow_router
from app.api.routes.email_security import router as email_security_router
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
from app.api.routes.routing import router as routing_router
from app.api.routes.estimates import router as estimates_router
from app.api.routes.project_pricing import router as project_pricing_router
from app.api.routes.materials import router as materials_router
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
from app.workers.interpretation_worker import run_interpretation_worker
from app.services.project_service import ProjectNotFoundError
from sqlalchemy.exc import SQLAlchemyError


@asynccontextmanager
async def lifespan(application: FastAPI):
    reset_stop=threading.Event()
    reset_thread=None
    worker_thread = None
    stop_event = None
    settings = application.state.settings
    if settings.database_url and settings.database_url==get_settings().database_url:
        from app.services.workspace_reset import run_worker
        reset_thread=threading.Thread(target=run_worker,args=(reset_stop,),daemon=True,name='ved-workspace-reset')
        reset_thread.start()
    if (
        settings.auto_start_interpretation_worker
        and settings.app_env == "development"
    ):
        stop_event = threading.Event()
        worker_thread = threading.Thread(
            target=run_interpretation_worker,
            kwargs={
                "stop_event": stop_event,
                "worker_identity": f"interpretation-worker:{os.getpid()}",
                "settings": settings,
            },
            daemon=True,
            name="ved-interpretation-worker",
        )
        worker_thread.start()
    try:
        yield
    finally:
        reset_stop.set()
        if reset_thread is not None:await asyncio.to_thread(reset_thread.join,5)
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
    @application.exception_handler(ProjectNotFoundError)
    async def missing_project(_request, _error):
        return JSONResponse(status_code=404, content={'detail': 'Project not found.'})

    @application.exception_handler(SQLAlchemyError)
    async def storage_error(_request, _error):
        return JSONResponse(status_code=503, content={'detail': 'Storage is temporarily unavailable. Reload and try again.'})
    @application.exception_handler(RequestValidationError)
    async def request_validation_error(request: Request, error: RequestValidationError):
        # Credentials must never be echoed by FastAPI's default validation response.
        if request.url.path.startswith(('/api/auth/', '/api/admin/clients', '/api/admin/accounts')):
            mismatch=any('passwords do not match' in str(item.get('ctx',{}).get('error','')) or 'confirm_password' in item.get('loc',()) for item in error.errors())
            message='Enter the same password in both password fields.' if mismatch else 'Enter a valid verified email address.' if request.url.path.endswith('/recover') else 'Check the account details and password requirements and try again.'
            return JSONResponse(status_code=422, content={'detail': message})
        return await request_validation_exception_handler(request, error)
    protect_auth_access_logs()
    application.add_exception_handler(StarletteHTTPException,auth_exception_handler)

    try:
        oauth_configuration = get_oauth_oidc_configuration(application_settings)
    except OAuthOIDCConfigurationError as error:
        application.state.oauth_oidc_configuration = None
        application.state.oauth_oidc_configuration_error = str(error)
    else:
        application.state.oauth_oidc_configuration = oauth_configuration
        application.state.oauth_oidc_configuration_error = None
    if application_settings.session_secret and len(application_settings.session_secret.get_secret_value()) >= 32:
        application.add_middleware(
            SessionMiddleware,
            secret_key=application_settings.session_secret.get_secret_value(),
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
    application.include_router(application_defaults_router)
    application.include_router(material_assemblies_router)
    application.include_router(analysis_settings_router)
    application.include_router(dataset_approver_router)
    application.include_router(dataset_approver_admin_router)
    application.include_router(demo_interpretation_router)
    application.include_router(auth_router)
    application.include_router(email_security_router)
    application.include_router(client_workflow_router)
    application.include_router(projects_router)
    application.include_router(project_floors_router)
    application.include_router(layouts_router)
    application.include_router(routing_router)
    application.include_router(estimates_router)
    application.include_router(project_pricing_router)
    application.include_router(materials_router)
    application.include_router(floor_plans_router)
    application.include_router(processing_router)
    application.include_router(detections_router)
    application.include_router(manual_symbols_router)
    application.include_router(review_images_router)
    application.include_router(symbol_legends_router)
    application.include_router(symbol_legend_admin_router)
    from app.api.routes.draft_approvals import router as draft_approvals_router
    application.include_router(draft_approvals_router)
    from app.api.routes.notifications import router as notifications_router
    application.include_router(notifications_router)
    from app.api.routes.workspace_reset import router as workspace_reset_router
    application.include_router(workspace_reset_router)
    return application


app = create_app()
