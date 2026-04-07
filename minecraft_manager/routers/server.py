from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from minecraft_manager.dependencies import get_settings
from minecraft_manager.services import server_control
from minecraft_manager.services.server_status import get_server_status

router = APIRouter(prefix="/server")


async def _action_response(request: Request) -> HTMLResponse:
    settings = get_settings()
    status = await get_server_status(settings)
    return request.app.state.templates.TemplateResponse(
        request, "partials/server_status.html",
        {"status": status},
    )


@router.post("/start", response_class=HTMLResponse)
async def start(request: Request):
    settings = get_settings()
    await server_control.start_server(settings)
    return await _action_response(request)


@router.post("/stop", response_class=HTMLResponse)
async def stop(request: Request):
    settings = get_settings()
    await server_control.stop_server(settings)
    return await _action_response(request)


@router.post("/restart", response_class=HTMLResponse)
async def restart(request: Request):
    settings = get_settings()
    await server_control.restart_server(settings)
    return await _action_response(request)
