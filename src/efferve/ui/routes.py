"""UI page routes and HTMX partial endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from efferve.alerts.manager import create_rule, delete_rule, list_rules, update_rule
from efferve.alerts.models import AlertRule
from efferve.config import load_config, save_config, settings
from efferve.database import get_session
from efferve.persona.engine import (
    assign_device,
    create_person,
    delete_person,
    get_present_persons,
    list_persons,
    unassign_device,
)
from efferve.persona.models import Person
from efferve.registry.models import DeviceClassification
from efferve.registry.store import get_all_devices, get_device, get_present_devices, set_display_name
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


# People page
@router.get("/people", response_class=HTMLResponse)
def people_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    persons = get_present_persons(session, grace_seconds=settings.presence_grace_period)
    all_devices = get_all_devices(session)
    return templates.TemplateResponse(
        "people.html",
        {
            "request": request,
            "persons": persons,
            "all_devices": all_devices,
        },
    )


# People partials
@router.get("/partials/people", response_class=HTMLResponse)
def partial_people(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    persons = get_present_persons(session, grace_seconds=settings.presence_grace_period)
    all_devices = get_all_devices(session)
    return templates.TemplateResponse(
        "partials/people_list.html",
        {
            "request": request,
            "persons": persons,
            "all_devices": all_devices,
        },
    )


@router.post("/people/add", response_class=HTMLResponse)
def add_person(
    request: Request,
    name: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if name.strip():
        create_person(session, name.strip())
    # Return updated people list partial
    persons = get_present_persons(session, grace_seconds=settings.presence_grace_period)
    all_devices = get_all_devices(session)
    return templates.TemplateResponse(
        "partials/people_list.html",
        {
            "request": request,
            "persons": persons,
            "all_devices": all_devices,
        },
    )


@router.post("/people/{person_id}/assign", response_class=HTMLResponse)
def assign_device_ui(
    request: Request,
    person_id: int,
    mac_address: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if mac_address.strip():
        try:
            assign_device(session, person_id, mac_address.strip())
        except ValueError:
            pass  # silently ignore — device not found or already assigned
    persons = get_present_persons(session, grace_seconds=settings.presence_grace_period)
    all_devices = get_all_devices(session)
    return templates.TemplateResponse(
        "partials/people_list.html",
        {
            "request": request,
            "persons": persons,
            "all_devices": all_devices,
        },
    )


@router.delete("/people/{person_id}/unassign/{mac}", response_class=HTMLResponse)
def unassign_device_ui(
    request: Request,
    person_id: int,
    mac: str,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    unassign_device(session, person_id, mac)
    persons = get_present_persons(session, grace_seconds=settings.presence_grace_period)
    all_devices = get_all_devices(session)
    return templates.TemplateResponse(
        "partials/people_list.html",
        {
            "request": request,
            "persons": persons,
            "all_devices": all_devices,
        },
    )


@router.delete("/people/{person_id}", response_class=HTMLResponse)
def delete_person_ui(
    request: Request,
    person_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    delete_person(session, person_id)
    persons = get_present_persons(session, grace_seconds=settings.presence_grace_period)
    all_devices = get_all_devices(session)
    return templates.TemplateResponse(
        "partials/people_list.html",
        {
            "request": request,
            "persons": persons,
            "all_devices": all_devices,
        },
    )


# Alerts page
@router.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    rules = list_rules(session)
    return templates.TemplateResponse(
        "alerts.html",
        {
            "request": request,
            "rules": rules,
        },
    )


@router.get("/partials/alerts", response_class=HTMLResponse)
def partial_alerts(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    rules = list_rules(session)
    return templates.TemplateResponse(
        "partials/alerts_list.html",
        {
            "request": request,
            "rules": rules,
        },
    )


@router.post("/alerts/add", response_class=HTMLResponse)
def add_alert_rule(
    request: Request,
    name: str = Form(""),
    webhook_url: str = Form(""),
    trigger_type: str = Form("both"),
    person_id: str = Form(""),
    mac_address: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    if name.strip() and webhook_url.strip():
        create_rule(
            session,
            name=name.strip(),
            webhook_url=webhook_url.strip(),
            trigger_type=trigger_type,
            person_id=int(person_id) if person_id.strip() else None,
            mac_address=mac_address.strip() or None,
        )
    rules = list_rules(session)
    return templates.TemplateResponse(
        "partials/alerts_list.html",
        {
            "request": request,
            "rules": rules,
        },
    )


@router.post("/alerts/{rule_id}/toggle", response_class=HTMLResponse)
def toggle_alert_rule(
    request: Request,
    rule_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    from efferve.alerts.manager import get_rule

    rule = get_rule(session, rule_id)
    if rule:
        update_rule(session, rule_id, enabled=not rule.enabled)
    rules = list_rules(session)
    return templates.TemplateResponse(
        "partials/alerts_list.html",
        {
            "request": request,
            "rules": rules,
        },
    )


@router.delete("/alerts/{rule_id}/delete", response_class=HTMLResponse)
def delete_alert_rule_ui(
    request: Request,
    rule_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    delete_rule(session, rule_id)
    rules = list_rules(session)
    return templates.TemplateResponse(
        "partials/alerts_list.html",
        {
            "request": request,
            "rules": rules,
        },
    )


# Device naming
@router.get("/partials/device-name-edit/{mac}", response_class=HTMLResponse)
def device_name_edit_form(
    request: Request,
    mac: str,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    device = get_device(session, mac)
    return templates.TemplateResponse(
        "partials/device_name_edit.html",
        {
            "request": request,
            "device": device,
        },
    )


@router.post("/devices/{mac}/name", response_class=HTMLResponse)
def save_device_name(
    request: Request,
    mac: str,
    display_name: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    set_display_name(session, mac, display_name.strip())
    # Return the updated device row partial
    device = get_device(session, mac)
    return templates.TemplateResponse(
        "partials/device_row.html",
        {
            "request": request,
            "device": device,
        },
    )
