"""UI page routes and HTMX partial endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from efferve.config import settings
from efferve.database import get_session
from efferve.registry.models import DeviceClassification
from efferve.registry.store import get_all_devices, get_present_devices

_template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    grace = settings.presence_grace_period
    devices = get_present_devices(session, grace_seconds=grace)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "devices": devices, "present_count": len(devices)},
    )


@router.get("/devices", response_class=HTMLResponse)
def device_list(
    request: Request,
    classification: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    cls_filter = None
    if classification and classification in DeviceClassification.__members__:
        cls_filter = DeviceClassification(classification)
    devices = get_all_devices(session, classification=cls_filter)
    return templates.TemplateResponse(
        "devices.html",
        {
            "request": request,
            "devices": devices,
            "active_filter": classification or "all",
        },
    )


@router.get("/partials/presence", response_class=HTMLResponse)
def partial_presence(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    grace = settings.presence_grace_period
    devices = get_present_devices(session, grace_seconds=grace)
    return templates.TemplateResponse(
        "partials/presence_list.html",
        {"request": request, "devices": devices, "present_count": len(devices)},
    )


@router.get("/partials/device-table", response_class=HTMLResponse)
def partial_device_table(
    request: Request,
    classification: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    cls_filter = None
    if classification and classification in DeviceClassification.__members__:
        cls_filter = DeviceClassification(classification)
    devices = get_all_devices(session, classification=cls_filter)
    return templates.TemplateResponse(
        "partials/device_table.html",
        {"request": request, "devices": devices},
    )
