from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.analysis_settings import router as analysis_settings_router
from app.api.routes.detections import router as detections_router
from app.api.routes.floor_plans import router as floor_plans_router
from app.api.routes.health import router as health_router
from app.api.routes.layouts import router as layouts_router
from app.api.routes.manual_symbols import router as manual_symbols_router
from app.api.routes.processing import router as processing_router
from app.api.routes.project_floors import router as project_floors_router
from app.api.routes.projects import router as projects_router
from app.api.routes.review_images import router as review_images_router
from app.api.routes.symbol_legends import router as symbol_legends_router
from app.core.config import (
    OAuthOIDCConfigurationError,
    Settings,
    get_cors_allowed_origins,
    get_oauth_oidc_configuration,
    get_settings,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    application_settings = settings or get_settings()
    application = FastAPI(
        title=f"{application_settings.app_name} API",
        debug=application_settings.app_debug,
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
    return application


app = create_app()
