from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title=f"{settings.app_name} API",
    debug=settings.app_debug,
)
app.state.settings = settings
app.include_router(health_router)
