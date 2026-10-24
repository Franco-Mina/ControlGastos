"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import BASE_DIR, settings
from app.db import SessionLocal
from app.routers import dashboard, expenses
from app.seed import seed_categories
from app.templating import templates

STATIC_DIR = Path(BASE_DIR) / "app" / "static"


def upgrade_database() -> None:
    """Bring the SQLite schema up to date before serving requests."""
    config = Config(str(Path(BASE_DIR) / "alembic.ini"))
    config.set_main_option("script_location", str(Path(BASE_DIR) / "migrations"))
    command.upgrade(config, "head")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    upgrade_database()
    with SessionLocal() as session:
        seed_categories(session)
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(dashboard.router)
app.include_router(expenses.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Render a Spanish page for 404s; keep other errors as JSON."""
    if exc.status_code == 404:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={},
            status_code=404,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
