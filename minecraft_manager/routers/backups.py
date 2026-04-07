from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from minecraft_manager.dependencies import get_settings
from minecraft_manager.services import backup as backup_service
from minecraft_manager.services.server_status import get_server_status

router = APIRouter(prefix="/backups")


@router.get("", response_class=HTMLResponse)
async def backups_page(request: Request):
    settings = get_settings()
    backups = backup_service.list_backups(settings)
    status = await get_server_status(settings)
    return request.app.state.templates.TemplateResponse(
        "backups.html",
        {
            "request": request,
            "active_page": "backups",
            "backups": backups,
            "server_running": status.running,
        },
    )


@router.get("/list", response_class=HTMLResponse)
async def backup_list_partial(request: Request):
    settings = get_settings()
    backup_type = request.query_params.get("type")
    backups = backup_service.list_backups(settings, backup_type)
    return request.app.state.templates.TemplateResponse(
        "partials/backup_list.html",
        {"request": request, "backups": backups},
    )


@router.post("/create", response_class=HTMLResponse)
async def create_backup(request: Request):
    settings = get_settings()
    form = await request.form()
    backup_type = str(form.get("backup_type", "daily"))
    status = await get_server_status(settings)

    entry = await backup_service.create_backup(
        settings,
        backup_type=backup_type,
        is_server_running=status.running,
    )

    backup_service.apply_retention(settings)
    backups = backup_service.list_backups(settings)

    message = f"Backup created: {entry.filename}" if entry else "Backup failed"
    msg_type = "success" if entry else "error"

    return request.app.state.templates.TemplateResponse(
        "partials/backup_list.html",
        {"request": request, "backups": backups, "flash": message, "flash_type": msg_type},
    )


@router.post("/restore", response_class=HTMLResponse)
async def restore_backup(request: Request):
    settings = get_settings()
    form = await request.form()
    backup_path = str(form.get("backup_path", ""))
    is_world = form.get("is_world") == "true"

    # Stop server before restore
    from minecraft_manager.services.server_control import stop_server, start_server

    status = await get_server_status(settings)
    was_running = status.running
    if was_running:
        await stop_server(settings)

    ok, msg = await backup_service.restore_backup(settings, backup_path, is_world)

    if was_running:
        await start_server(settings)

    backups = backup_service.list_backups(settings)
    return request.app.state.templates.TemplateResponse(
        "partials/backup_list.html",
        {"request": request, "backups": backups, "flash": msg, "flash_type": "success" if ok else "error"},
    )


@router.delete("/{backup_path:path}", response_class=HTMLResponse)
async def delete_backup(backup_path: str, request: Request):
    ok, msg = backup_service.delete_backup(backup_path)
    settings = get_settings()
    backups = backup_service.list_backups(settings)
    return request.app.state.templates.TemplateResponse(
        "partials/backup_list.html",
        {"request": request, "backups": backups, "flash": msg, "flash_type": "success" if ok else "error"},
    )
