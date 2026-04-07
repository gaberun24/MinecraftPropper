from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from minecraft_manager.dependencies import get_settings
from minecraft_manager.services.update import apply_update, check_updates, read_installed_versions

router = APIRouter(prefix="/updates")


@router.get("", response_class=HTMLResponse)
async def updates_page(request: Request):
    settings = get_settings()
    installed = read_installed_versions(settings)
    return request.app.state.templates.TemplateResponse(
        request, "updates.html",
        {
            "active_page": "updates",
            "installed": installed,
            "check": None,
        },
    )


@router.get("/check", response_class=HTMLResponse)
async def check_updates_partial(request: Request):
    settings = get_settings()
    installed = read_installed_versions(settings)
    try:
        update_check = await check_updates(settings)
    except Exception as e:
        update_check = None
        installed["_error"] = str(e)

    return request.app.state.templates.TemplateResponse(
        request, "partials/update_status.html",
        {
            "installed": installed,
            "check": update_check,
        },
    )


@router.post("/apply/{component}", response_class=HTMLResponse)
async def apply_update_endpoint(component: str, request: Request):
    settings = get_settings()

    update_check = await check_updates(settings)

    build = None
    if component == "paper" and update_check.paper:
        build = update_check.paper
    elif component == "geyser" and update_check.geyser:
        build = update_check.geyser
    elif component == "floodgate" and update_check.floodgate:
        build = update_check.floodgate

    if not build:
        return HTMLResponse(
            '<div class="flash error">No update available for this component</div>'
        )

    messages = []
    async for msg in apply_update(settings, component, build):
        messages.append(msg)

    installed = read_installed_versions(settings)
    result_msg = messages[-1] if messages else "Update completed"
    is_error = any("ERROR" in m for m in messages)

    return request.app.state.templates.TemplateResponse(
        request, "partials/update_status.html",
        {
            "installed": installed,
            "check": None,
            "flash": result_msg,
            "flash_type": "error" if is_error else "success",
        },
    )
