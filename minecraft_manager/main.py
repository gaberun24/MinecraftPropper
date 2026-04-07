from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from minecraft_manager.routers import backups, console, dashboard, server, settings, updates, worlds

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(title="Minecraft Manager")

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.state.templates = templates

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    app.include_router(dashboard.router)
    app.include_router(server.router)
    app.include_router(console.router)
    app.include_router(backups.router)
    app.include_router(updates.router)
    app.include_router(worlds.router)
    app.include_router(settings.router)

    return app


app = create_app()
