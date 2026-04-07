from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse

from minecraft_manager.dependencies import get_settings
from minecraft_manager.services import world as world_service

router = APIRouter(prefix="/worlds")


def _world_list_response(request: Request, flash: str = "", flash_type: str = "success"):
    settings = get_settings()
    worlds = world_service.list_worlds(settings)
    ctx = {"worlds": worlds}
    if flash:
        ctx["flash"] = flash
        ctx["flash_type"] = flash_type
    return request.app.state.templates.TemplateResponse(
        request, "partials/world_list.html", ctx,
    )


@router.get("", response_class=HTMLResponse)
async def worlds_page(request: Request):
    settings = get_settings()
    worlds = world_service.list_worlds(settings)
    return request.app.state.templates.TemplateResponse(
        request, "worlds.html",
        {"active_page": "worlds", "worlds": worlds},
    )


@router.get("/list", response_class=HTMLResponse)
async def world_list_partial(request: Request):
    return _world_list_response(request)


@router.post("/{name}/activate", response_class=HTMLResponse)
async def activate(name: str, request: Request):
    settings = get_settings()
    ok, msg = await world_service.activate_world(settings, name)
    return _world_list_response(request, msg, "success" if ok else "error")


@router.post("/{name}/snapshot", response_class=HTMLResponse)
async def snapshot(name: str, request: Request):
    settings = get_settings()
    ok, msg = await world_service.snapshot_world(settings, name)
    return _world_list_response(request, msg, "success" if ok else "error")


@router.post("/{name}/restore", response_class=HTMLResponse)
async def restore(name: str, request: Request):
    settings = get_settings()
    form = await request.form()
    snapshot_path = str(form.get("snapshot_path", ""))
    ok, msg = await world_service.restore_snapshot(settings, name, snapshot_path)
    return _world_list_response(request, msg, "success" if ok else "error")


@router.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, name: str = Form(...), file: UploadFile = File(...)):
    settings = get_settings()
    content = await file.read()
    ok, msg = await world_service.upload_world(settings, name, content)
    return _world_list_response(request, msg, "success" if ok else "error")


@router.get("/{name}/download")
async def download(name: str):
    settings = get_settings()
    path = await world_service.download_world(settings, name)
    if not path:
        return HTMLResponse("World not found", status_code=404)
    return FileResponse(
        path=str(path),
        filename=f"{name}.tar.gz",
        media_type="application/gzip",
    )


@router.post("/{name}/duplicate", response_class=HTMLResponse)
async def duplicate(name: str, request: Request):
    form = await request.form()
    new_name = str(form.get("new_name", ""))
    settings = get_settings()
    ok, msg = await world_service.duplicate_world(settings, name, new_name)
    return _world_list_response(request, msg, "success" if ok else "error")


@router.post("/{name}/rename", response_class=HTMLResponse)
async def rename(name: str, request: Request):
    form = await request.form()
    new_name = str(form.get("new_name", ""))
    settings = get_settings()
    ok, msg = await world_service.rename_world(settings, name, new_name)
    return _world_list_response(request, msg, "success" if ok else "error")


@router.delete("/{name}", response_class=HTMLResponse)
async def delete(name: str, request: Request):
    settings = get_settings()
    ok, msg = await world_service.delete_world(settings, name)
    return _world_list_response(request, msg, "success" if ok else "error")
