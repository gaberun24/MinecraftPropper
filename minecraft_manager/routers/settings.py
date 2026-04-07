import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from minecraft_manager.dependencies import get_settings

router = APIRouter(prefix="/settings")


def _load_manager_settings(settings) -> dict:
    path = settings.settings_file_path
    if path.exists():
        return json.loads(path.read_text())
    return {
        "auto_update_enabled": settings.auto_update_enabled,
        "daily_retention": settings.daily_retention,
        "builds_to_keep": settings.builds_to_keep,
        "health_check_timeout": settings.health_check_timeout,
        "player_notify_seconds": settings.player_notify_seconds,
    }


def _save_manager_settings(settings, data: dict) -> None:
    path = settings.settings_file_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request):
    settings = get_settings()
    mgr_settings = _load_manager_settings(settings)
    return request.app.state.templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "active_page": "settings",
            "mgr": mgr_settings,
            "settings": settings,
        },
    )


@router.post("", response_class=HTMLResponse)
async def save_settings(request: Request):
    settings = get_settings()
    form = await request.form()

    mgr_settings = {
        "auto_update_enabled": form.get("auto_update_enabled") == "on",
        "daily_retention": int(form.get("daily_retention", 7)),
        "builds_to_keep": int(form.get("builds_to_keep", 5)),
        "health_check_timeout": int(form.get("health_check_timeout", 90)),
        "player_notify_seconds": int(form.get("player_notify_seconds", 30)),
    }

    _save_manager_settings(settings, mgr_settings)

    return request.app.state.templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "active_page": "settings",
            "mgr": mgr_settings,
            "settings": settings,
            "flash": "Settings saved",
            "flash_type": "success",
        },
    )
