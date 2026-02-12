"""UI page routes and HTMX partial endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from efferve.config import load_config, save_config, settings
from efferve.database import get_session
from efferve.registry.models import DeviceClassification
from efferve.registry.store import get_all_devices, get_present_devices
from efferve.sniffer.test_connection import test_glinet, test_opnsense, test_ruckus

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


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request) -> HTMLResponse:
    config = load_config()
    return templates.TemplateResponse(
        "setup.html",
        {"request": request, "config": config},
    )


@router.post("/setup/test/ruckus", response_class=HTMLResponse)
async def test_ruckus_connection(
    request: Request,
    ruckus_host: str = Form(""),
    ruckus_username: str = Form(""),
    ruckus_password: str = Form(""),
) -> HTMLResponse:
    result = await test_ruckus(ruckus_host, ruckus_username, ruckus_password)
    return templates.TemplateResponse(
        "partials/connection_result.html",
        {"request": request, "success": result.success, "message": result.message},
    )


@router.post("/setup/test/opnsense", response_class=HTMLResponse)
async def test_opnsense_connection(
    request: Request,
    opnsense_url: str = Form(""),
    opnsense_api_key: str = Form(""),
    opnsense_api_secret: str = Form(""),
) -> HTMLResponse:
    result = await test_opnsense(opnsense_url, opnsense_api_key, opnsense_api_secret)
    return templates.TemplateResponse(
        "partials/connection_result.html",
        {"request": request, "success": result.success, "message": result.message},
    )


@router.post("/setup/test/glinet", response_class=HTMLResponse)
async def test_glinet_connection(
    request: Request,
    glinet_host: str = Form(""),
    glinet_username: str = Form("root"),
    glinet_password: str = Form(""),
) -> HTMLResponse:
    result = await test_glinet(glinet_host, glinet_username, glinet_password)
    return templates.TemplateResponse(
        "partials/connection_result.html",
        {"request": request, "success": result.success, "message": result.message},
    )


@router.post("/setup/save")
async def save_setup(
    request: Request,
    ruckus_host: str = Form(""),
    ruckus_username: str = Form(""),
    ruckus_password: str = Form(""),
    opnsense_url: str = Form(""),
    opnsense_api_key: str = Form(""),
    opnsense_api_secret: str = Form(""),
    glinet_host: str = Form(""),
    glinet_username: str = Form("root"),
    glinet_password: str = Form(""),
    glinet_wifi_interface: str = Form("wlan0"),
    glinet_monitor_interface: str = Form("wlan0mon"),
    poll_interval: int = Form(30),
    presence_grace_period: int = Form(180),
) -> Response:
    from efferve.main import restart_sniffer

    # Build sniffer_modes from all backends with credentials
    modes: list[str] = []
    if ruckus_host and ruckus_username and ruckus_password:
        modes.append("ruckus")
    if opnsense_url and opnsense_api_key and opnsense_api_secret:
        modes.append("opnsense")
    if glinet_host and glinet_password:
        modes.append("glinet")

    values = {
        "sniffer_modes": modes,
        "ruckus_host": ruckus_host or None,
        "ruckus_username": ruckus_username or None,
        "ruckus_password": ruckus_password or None,
        "opnsense_url": opnsense_url or None,
        "opnsense_api_key": opnsense_api_key or None,
        "opnsense_api_secret": opnsense_api_secret or None,
        "glinet_host": glinet_host or None,
        "glinet_username": glinet_username or None,
        "glinet_password": glinet_password or None,
        "glinet_wifi_interface": glinet_wifi_interface,
        "glinet_monitor_interface": glinet_monitor_interface,
        "poll_interval": poll_interval,
        "presence_grace_period": presence_grace_period,
    }
    save_config(values)
    await restart_sniffer(request.app)
    return Response(status_code=200, headers={"HX-Redirect": "/"})
