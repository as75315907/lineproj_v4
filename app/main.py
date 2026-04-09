from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.webhook import router as webhook_router
from app.core.config import settings
from app.core.db import init_db

app = FastAPI(title=settings.app_name, debug=settings.app_debug)
init_db()


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(webhook_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
