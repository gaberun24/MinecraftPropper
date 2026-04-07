import asyncio

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from minecraft_manager.dependencies import get_settings
from minecraft_manager.services.console import send_command, tail_log

router = APIRouter()


@router.get("/console", response_class=HTMLResponse)
async def console_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "console.html",
        {"request": request, "active_page": "console"},
    )


@router.websocket("/console/ws")
async def console_ws(websocket: WebSocket):
    await websocket.accept()
    settings = get_settings()

    async def send_logs():
        try:
            async for line in tail_log(settings):
                await websocket.send_text(line)
        except (WebSocketDisconnect, Exception):
            pass

    log_task = asyncio.create_task(send_logs())

    try:
        while True:
            data = await websocket.receive_text()
            command = data.strip()
            if command:
                await send_command(command, settings)
    except WebSocketDisconnect:
        pass
    finally:
        log_task.cancel()
        try:
            await log_task
        except asyncio.CancelledError:
            pass


@router.post("/console/command", response_class=HTMLResponse)
async def send_console_command(request: Request):
    form = await request.form()
    command = str(form.get("command", "")).strip()
    settings = get_settings()
    if command:
        await send_command(command, settings)
    return HTMLResponse(content="")
