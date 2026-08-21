from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.core.config import (
    OAuthOIDCConfigurationError,
    Settings,
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

    application.include_router(health_router)
    application.include_router(auth_router)
    return application


app = create_app()
