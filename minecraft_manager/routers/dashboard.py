from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from minecraft_manager.dependencies import get_settings
from minecraft_manager.services.server_status import get_server_status

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    settings = get_settings()
    status = await get_server_status(settings)
    return request.app.state.templates.TemplateResponse(
        request, "dashboard.html",
        {"status": status, "active_page": "dashboard"},
    )


@router.get("/api/status", response_class=HTMLResponse)
async def status_partial(request: Request):
    settings = get_settings()
    status = await get_server_status(settings)
    return request.app.state.templates.TemplateResponse(
        request, "partials/server_status.html",
        {"status": status},
    )
